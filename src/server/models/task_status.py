from collections import deque
from threading import Lock


class TaskStatus:
    def __init__(self, max_lines=300):
        self._lock = Lock()
        self._running = False
        self._error = False
        self._message = ""
        self._output = deque(maxlen=max_lines)

    def start(self, message="Iniciando..."):
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._error = False
            self._message = message
            self._output.clear()
            return True

    def append(self, line):
        with self._lock:
            self._output.append(line.rstrip("\n"))

    def finish(self, success, message):
        with self._lock:
            self._running = False
            self._error = not success
            self._message = message

    def restore(self, output, message):
        with self._lock:
            self._running = True
            self._error = False
            self._message = message
            self._output.clear()
            self._output.extend(output)

    def snapshot(self):
        with self._lock:
            return {
                "is_running": self._running,
                "error": self._error,
                "message": self._message,
                "output": list(self._output),
            }
