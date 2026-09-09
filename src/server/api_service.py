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
progress = ProgressReporter(str(PROJECT_ROOT / ".update-futbollibre.progress.json"))
runner.recover()
mdns = MdnsAdvertiser(port=8080)
udp_discovery = UdpDiscoveryResponder(http_port=8080)
TV_APP_VERSION_CODE = int(os.getenv("TV_APP_VERSION_CODE", "2"))
TV_APP_VERSION_NAME = os.getenv("TV_APP_VERSION_NAME", "0.2")
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


def agenda_service():
    return AgendaService(dotenv_values(ENV_PATH))


@app.get("/")
@app.get("/ejecutar")
def executor_page():
    return render_template("executor.html", current_url=current_futbol_urls())


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
    if not new_url:
        return jsonify(success=False, error="URL no proporcionada."), 400
    if runner.is_running() or status.snapshot()["is_running"]:
        current_status = status.snapshot()
        current_status["is_running"] = True
        current_status["output"] = runner.tail_output()
        current_status["progress"] = progress.snapshot()
        return jsonify(success=False, error="Ya hay una actualización en curso.", running=True, status=current_status), 409
    try:
        urls_file = urls_env_path()
        urls_file.parent.mkdir(parents=True, exist_ok=True)
        set_key(str(urls_file), "FUTBOL_LIBRE_URL", new_url)
        progress.reset()
        if not runner.start("update-futbollibre.sh"):
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
    return ChannelService(
        configured_path("XML_FILE", "eventos.xml"),
        configured_path("M3U_FILE", "eventos.m3u"),
        configured_path("TV_EVENTS_FILE", "eventos.json"),
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
    return (
        "<!doctype html><meta charset='utf-8'>"
        "<title>Fútbol TV</title><h1>Fútbol TV</h1>"
        f"<p>Versión {TV_APP_VERSION_NAME}</p>"
        "<p><a href='/downloads/futbol-tv.apk'>Descargar APK para Android TV</a></p>"
    )


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
        if target == "ha":
            message = agenda_service().update_home_assistant()
        elif target == "ntfy":
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
