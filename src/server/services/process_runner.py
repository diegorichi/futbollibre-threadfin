import os
import signal
import subprocess
import threading
import time


class ProcessRunner:
    def __init__(self, project_root, status):
        self.project_root = project_root
        self.status = status
        self.pid_file = os.path.join(project_root, ".update-futbollibre.pid")
        self.log_file = os.path.join(project_root, ".update-futbollibre.log")
        self._start_lock = threading.Lock()

    def start(self, script_name):
        with self._start_lock:
            if self.is_running():
                return False
            self._clear_log()
            if not self.status.start(f"Ejecutando {script_name}..."):
                return False
            thread = threading.Thread(target=self._run, args=(script_name,), daemon=True)
            thread.start()
            return True

    def recover(self):
        if self.is_running():
            self.status.restore(self.tail_output(), "Actualización detectada en curso.")

    def stop(self):
        with self._start_lock:
            pid = self._read_pid() or self._find_process_pid()
            if pid is None or not self._is_update_process(pid):
                return False
            try:
                process_group = os.getpgid(pid)
                if process_group == pid and process_group != os.getpgrp():
                    os.killpg(process_group, signal.SIGTERM)
                else:
                    os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                self._remove_pid(pid)
                return False

            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and self._pid_exists(pid):
                time.sleep(0.1)
            if self._pid_exists(pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self._remove_pid(pid)
            self.status.append("--- Proceso detenido por el usuario ---")
            self.status.finish(False, "Proceso detenido por el usuario.")
            return True

    def tail_output(self, max_lines=300):
        try:
            with open(self.log_file, encoding="utf-8", errors="replace") as log_file:
                return log_file.readlines()[-max_lines:]
        except FileNotFoundError:
            return []

    def is_running(self):
        pid = self._read_pid()
        if pid is None:
            pid = self._find_process_pid()
            if pid is None:
                return False
            self._write_pid(pid)
            return True
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, PermissionError, OSError):
            self._remove_pid(pid)
            return False

        command = self._process_command(pid)
        if command and "update-futbollibre.sh" in command:
            return True
        self._remove_pid(pid)
        pid = self._find_process_pid()
        if pid is None:
            return False
        self._write_pid(pid)
        return True

    def _run(self, script_name):
        script_path = os.path.join(self.project_root, script_name)
        process = None
        try:
            process = subprocess.Popen(
                ["bash", script_path],
                stdout=open(self.log_file, "a", encoding="utf-8", buffering=1),
                stderr=subprocess.STDOUT,
                cwd=self.project_root,
                start_new_session=True,
            )
            self._write_pid(process.pid)
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
        finally:
            if process is not None:
                self._remove_pid(process.pid)

    def _read_pid(self):
        try:
            with open(self.pid_file, encoding="utf-8") as pid_file:
                return int(pid_file.read().strip())
        except (FileNotFoundError, ValueError, OSError):
            return None

    def _is_update_process(self, pid):
        return "update-futbollibre.sh" in self._process_command(pid)

    @staticmethod
    def _pid_exists(pid):
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False

    def _clear_log(self):
        with open(self.log_file, "w", encoding="utf-8"):
            pass

    def _write_pid(self, pid):
        with open(self.pid_file, "w", encoding="utf-8") as pid_file:
            pid_file.write(str(pid))

    def _remove_pid(self, pid):
        try:
            if self._read_pid() == pid:
                os.remove(self.pid_file)
        except FileNotFoundError:
            pass

    @staticmethod
    def _process_command(pid):
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return ""
        return result.stdout.strip()

    @staticmethod
    def _find_process_pid():
        try:
            result = subprocess.run(
                ["ps", "-axo", "pid=,command="],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError:
            return None
        for line in result.stdout.splitlines():
            fields = line.strip().split(None, 1)
            if len(fields) == 2 and "update-futbollibre.sh" in fields[1]:
                try:
                    return int(fields[0])
                except ValueError:
                    continue
        return None
