import os
import subprocess
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key
from flask import Flask, jsonify, render_template, request, send_file

from server.models.task_status import TaskStatus
from server.services.agenda_service import AgendaService
from server.services.channel_service import ChannelService
from server.services.process_runner import ProcessRunner
from server.discovery import MdnsAdvertiser, UdpDiscoveryResponder
from progress import ProgressReporter


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = Path(os.getenv("ENV_FILE", PROJECT_ROOT / ".env"))
if not ENV_PATH.is_absolute():
    ENV_PATH = PROJECT_ROOT / ENV_PATH
load_dotenv(ENV_PATH)

app = Flask(__name__)
status = TaskStatus()
runner = ProcessRunner(str(PROJECT_ROOT), status)
PROGRESS_PATH = Path(os.getenv("PROGRESS_FILE", PROJECT_ROOT / ".update-futbollibre.progress.json"))
if not PROGRESS_PATH.is_absolute():
    PROGRESS_PATH = PROJECT_ROOT / PROGRESS_PATH
progress = ProgressReporter(str(PROGRESS_PATH))
runner.recover()
mdns = MdnsAdvertiser(port=8080)
udp_discovery = UdpDiscoveryResponder(http_port=8080)
TV_APP_VERSION_CODE = int(os.getenv("TV_APP_VERSION_CODE", "5"))
TV_APP_VERSION_NAME = os.getenv("TV_APP_VERSION_NAME", "0.5")
TV_APP_APK_PATH = Path(os.getenv("TV_APP_APK_PATH", PROJECT_ROOT / "output/futbol-tv-debug.apk"))
if not TV_APP_APK_PATH.is_absolute():
    TV_APP_APK_PATH = PROJECT_ROOT / TV_APP_APK_PATH


def configured_path(env_name, fallback):
    value = os.getenv(env_name)
    return Path(value) if value else PROJECT_ROOT / fallback


def urls_env_path():
    path = Path(os.getenv("FUTBOL_LIBRE_URL_FILE", PROJECT_ROOT / "futbol_libre_urls.env"))
    return path if path.is_absolute() else PROJECT_ROOT / path


def current_futbol_urls():
    values = dotenv_values(urls_env_path())
    return values.get("FUTBOL_LIBRE_URL") or os.getenv("FUTBOL_LIBRE_URL", "")


def current_extra_futbol_url():
    values = dotenv_values(urls_env_path())
    return values.get("FUTBOL_LIBRE_EXTRA_URL") or os.getenv("FUTBOL_LIBRE_EXTRA_URL", "")


def agenda_service():
    return AgendaService(dotenv_values(ENV_PATH))


@app.get("/")
@app.get("/ejecutar")
def executor_page():
    return render_template(
        "executor.html",
        current_url=current_futbol_urls(),
        current_extra_url=current_extra_futbol_url(),
    )


@app.get("/canales")
def channels_page():
    try:
        service = ChannelService(
            configured_path("XML_FILE", "eventos.xml"),
            configured_path("M3U_FILE", "eventos.m3u"),
        )
        return render_template(
            "channels.html",
            channels=service.list_channels(),
            source_dates=service.source_update_dates(),
        )
    except FileNotFoundError:
        return render_template(
            "channels.html",
            channels=[],
            source_dates={"xml": "No disponible", "m3u": "No disponible"},
        )


@app.get("/sistemas")
def systems_page():
    return render_template("systems.html")


@app.post("/update-url")
def update_url():
    data = request.get_json(silent=True) or {}
    new_url = (data.get("url") or "").strip()
    extra_url = (data.get("extra_url") or "").strip()
    only_extra = bool(data.get("only_extra"))
    if not new_url and not only_extra:
        return jsonify(success=False, error="URL no proporcionada."), 400
    if only_extra and not extra_url:
        return jsonify(success=False, error="La URL adicional es obligatoria."), 400
    if "," in extra_url:
        return jsonify(success=False, error="El sitio adicional debe ser una sola URL."), 400
    if runner.is_running() or status.snapshot()["is_running"]:
        current_status = status.snapshot()
        current_status["is_running"] = True
        current_status["output"] = runner.tail_output()
        current_status["progress"] = progress.snapshot()
        return jsonify(success=False, error="Ya hay una actualización en curso.", running=True, status=current_status), 409
    try:
        urls_file = urls_env_path()
        urls_file.parent.mkdir(parents=True, exist_ok=True)
        if not only_extra:
            set_key(str(urls_file), "FUTBOL_LIBRE_URL", new_url)
        set_key(str(urls_file), "FUTBOL_LIBRE_EXTRA_URL", extra_url)
        progress.reset()
        arguments = ["--extra-only"] if only_extra else []
        if not runner.start("update-futbollibre.sh", arguments):
            return jsonify(success=False, error="Ya hay una actualización en curso."), 409
        return jsonify(success=True)
    except Exception as error:
        return jsonify(success=False, error=str(error)), 500


@app.get("/status")
def task_status():
    current_status = status.snapshot()
    current_status["output"] = runner.tail_output()
    current_status["progress"] = progress.snapshot()
    if runner.is_running():
        current_status["is_running"] = True
        if not current_status["message"]:
            current_status["message"] = "Actualización detectada en curso."
    return jsonify(current_status)


@app.post("/stop-update")
def stop_update():
    if not runner.stop():
        return jsonify(success=False, error="No hay una actualización corriendo."), 404
    progress.fail("Proceso detenido por el usuario.")
    return jsonify(success=True, message="Proceso detenido.")


@app.get("/grilla")
def grid_api():
    try:
        channels = ChannelService(
            configured_path("XML_FILE", "eventos.xml"),
            configured_path("M3U_FILE", "eventos.m3u"),
        ).list_channels()
        return jsonify([channel.__dict__ for channel in channels])
    except FileNotFoundError:
        return jsonify([])


def tv_channel_service():
    # XML/M3U son la misma fuente que usa la web. eventos.json puede quedar
    # con starts_at de fallback y desalinear la grilla de la app TV.
    return ChannelService(
        configured_path("XML_FILE", "eventos.xml"),
        configured_path("M3U_FILE", "eventos.m3u"),
    )


@app.get("/api/v1/health")
def tv_health():
    return jsonify({"ok": True, "service": "futbol-server", "api_version": "v1"})


@app.get("/api/v1/events")
def tv_events():
    try:
        events = [asdict(event) for event in tv_channel_service().list_events()]
        return jsonify({
            "api_version": "v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "refresh_after": 60,
            "events": events,
        })
    except FileNotFoundError:
        return jsonify({"api_version": "v1", "generated_at": None, "refresh_after": 60, "events": []})


@app.get("/api/v1/discovery")
def tv_discovery():
    return jsonify({"name": "Futbol Server", "api_version": "v1", "events_path": "/api/v1/events"})


@app.get("/tvapp")
def tv_app_page():
    return render_template("tvapp.html", version=TV_APP_VERSION_NAME)


@app.get("/api/v1/app")
def tv_app_info():
    return jsonify({
        "api_version": "v1",
        "version_code": TV_APP_VERSION_CODE,
        "version_name": TV_APP_VERSION_NAME,
        "apk_url": "/downloads/futbol-tv.apk",
        "changelog": "Actualización de Fútbol TV",
    })


@app.get("/downloads/futbol-tv.apk")
def tv_app_download():
    if not TV_APP_APK_PATH.is_file():
        return jsonify({"ok": False, "error": "APK no disponible"}), 404
    return send_file(TV_APP_APK_PATH, as_attachment=True, download_name="futbol-tv.apk", mimetype="application/vnd.android.package-archive")


@app.post("/system-update/<target>")
def system_update(target):
    try:
        if target == "ntfy":
            message = agenda_service().update_ntfy()
        elif target == "sites":
            result = subprocess.run(
                [str(PROJECT_ROOT / "update-futbol-libre-sites.sh")],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if result.returncode:
                error = result.stderr.strip() or result.stdout.strip() or "Error desconocido."
                return jsonify(success=False, error=error), 502
            message = result.stdout.strip() or "Sitios actualizados."
        else:
            return jsonify(success=False, error="Sistema no soportado."), 404
        return jsonify(success=True, message=message)
    except Exception as error:
        return jsonify(success=False, error=str(error)), 502


if __name__ == "__main__":
    mdns.start()
    udp_discovery.start()
    try:
        app.run(host="0.0.0.0", port=8080)
    finally:
        mdns.stop()
        udp_discovery.stop()
