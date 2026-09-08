import json
import os
from threading import Lock


class ProgressReporter:
    def __init__(self, path):
        self.path = path
        self._lock = Lock()

    def reset(self):
        self._write({
            "stage": "starting",
            "sites": {"completed": 0, "total": 0, "percent": 0},
            "streams": {"completed": 0, "total": 0, "percent": 0},
            "message": "Iniciando...",
        })

    def update(self, stage, completed, total, message):
        current = self.snapshot()
        percent = 100 if total == 0 else round(completed * 100 / total)
        current["stage"] = stage
        current[stage] = {"completed": completed, "total": total, "percent": percent}
        current["message"] = message
        self._write(current)

    def complete(self, message="Actualización completa."):
        current = self.snapshot()
        for stage in ("sites", "streams"):
            current[stage]["completed"] = current[stage]["total"]
            current[stage]["percent"] = 100
        current["stage"] = "done"
        current["message"] = message
        self._write(current)

    def fail(self, message):
        current = self.snapshot()
        current["stage"] = "error"
        current["message"] = message
        self._write(current)

    def snapshot(self):
        try:
            with open(self.path, encoding="utf-8") as progress_file:
                return json.load(progress_file)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {
                "stage": "idle",
                "sites": {"completed": 0, "total": 0, "percent": 0},
                "streams": {"completed": 0, "total": 0, "percent": 0},
                "message": "Sin ejecución.",
            }

    def _write(self, data):
        temporary_path = f"{self.path}.tmp"
        with self._lock:
            with open(temporary_path, "w", encoding="utf-8") as progress_file:
                json.dump(data, progress_file, ensure_ascii=False)
            os.replace(temporary_path, self.path)
