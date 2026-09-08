import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key
from flask import Flask, jsonify, render_template, request

from server.models.task_status import TaskStatus
from server.services.agenda_service import AgendaService
from server.services.channel_service import ChannelService
from server.services.process_runner import ProcessRunner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = Path(os.getenv("ENV_FILE", PROJECT_ROOT / ".env"))
if not ENV_PATH.is_absolute():
    ENV_PATH = PROJECT_ROOT / ENV_PATH
load_dotenv(ENV_PATH)

app = Flask(__name__)
status = TaskStatus()
runner = ProcessRunner(str(PROJECT_ROOT), status)


def configured_path(env_name, fallback):
    value = os.getenv(env_name)
    return Path(value) if value else PROJECT_ROOT / fallback


def agenda_service():
    return AgendaService(dotenv_values(ENV_PATH))


@app.get("/")
@app.get("/ejecutar")
def executor_page():
    return render_template("executor.html", current_url=os.getenv("FUTBOL_LIBRE_URL", ""))


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
        return jsonify(success=False, error="Ya hay una actualización en curso."), 409
    try:
        set_key(str(ENV_PATH), "FUTBOL_LIBRE_URL", new_url)
        if not runner.start("update-futbollibre.sh"):
            return jsonify(success=False, error="Ya hay una actualización en curso."), 409
        return jsonify(success=True)
    except Exception as error:
        return jsonify(success=False, error=str(error)), 500


@app.get("/status")
def task_status():
    current_status = status.snapshot()
    if runner.is_running():
        current_status["is_running"] = True
        if not current_status["message"]:
            current_status["message"] = "Actualización detectada en curso."
    return jsonify(current_status)


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


@app.post("/system-update/<target>")
def system_update(target):
    try:
        if target == "ha":
            message = agenda_service().update_home_assistant()
        elif target == "ntfy":
            message = agenda_service().update_ntfy()
        else:
            return jsonify(success=False, error="Sistema no soportado."), 404
        return jsonify(success=True, message=message)
    except Exception as error:
        return jsonify(success=False, error=str(error)), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
