"""Best-effort mDNS advertisement for the TV client."""

import logging
import socket
import threading


LOGGER = logging.getLogger(__name__)


class MdnsAdvertiser:
    SERVICE_TYPE = "_futbol._tcp.local."

    def __init__(self, port, name="Futbol Server"):
        self.port = port
        self.name = name
        self._zeroconf = None
        self._service = None
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._register, daemon=True)
        self._thread.start()

    def _register(self):
        try:
            from zeroconf import ServiceInfo, Zeroconf

            address = self._local_address()
            service_name = f"{self.name}.{self.SERVICE_TYPE}"
            self._service = ServiceInfo(
                self.SERVICE_TYPE,
                service_name,
                addresses=[socket.inet_aton(address)],
                port=self.port,
                properties={b"api": b"v1", b"name": self.name.encode("utf-8")},
            )
            self._zeroconf = Zeroconf()
            self._zeroconf.register_service(self._service)
            LOGGER.info("Servicio mDNS publicado como %s", service_name)
        except ImportError:
            LOGGER.warning("mDNS desactivado: instalar dependencia zeroconf para publicar el server")
        except Exception:
            LOGGER.exception("No se pudo publicar el servicio mDNS")

    @staticmethod
    def _local_address():
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        finally:
            sock.close()

    def stop(self):
        if self._zeroconf is not None:
            self._zeroconf.unregister_service(self._service)
            self._zeroconf.close()
            self._zeroconf = None
