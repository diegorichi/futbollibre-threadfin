import os
import subprocess
import threading


class ProcessRunner:
    def __init__(self, project_root, status):
        self.project_root = project_root
        self.status = status

    def start(self, script_name):
        if not self.status.start(f"Ejecutando {script_name}..."):
            return False
        thread = threading.Thread(target=self._run, args=(script_name,), daemon=True)
        thread.start()
        return True

    def _run(self, script_name):
        script_path = os.path.join(self.project_root, script_name)
        try:
            process = subprocess.Popen(
                ["bash", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.project_root,
                bufsize=1,
            )
            for line in iter(process.stdout.readline, ""):
                if line:
                    self.status.append(line)
            process.stdout.close()
            return_code = process.wait()
            success = return_code == 0
            message = "Terminado." if success else f"Falló con código {return_code}."
            self.status.append(
                "--- Proceso finalizado con éxito ---" if success
                else f"--- El script reportó un fallo (Código {return_code}) ---"
            )
            self.status.finish(success, message)
        except Exception as error:
            self.status.append(f"Error interno: {error}")
            self.status.finish(False, str(error))
