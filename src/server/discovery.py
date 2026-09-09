"""Best-effort mDNS advertisement for the TV client."""

import logging
import json
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


class UdpDiscoveryResponder:
    """LAN broadcast fallback for networks/LXCs where mDNS is filtered."""

    PORT = 45678
    REQUEST = b"FUTBOL_DISCOVER_V1"

    def __init__(self, http_port, name="Futbol Server"):
        self.http_port = http_port
        self.name = name
        self._stop = threading.Event()
        self._socket = None
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(("0.0.0.0", self.PORT))
            self._socket.settimeout(1)
            response = json.dumps({
                "name": self.name,
                "api_version": "v1",
                "port": self.http_port,
            }).encode("utf-8")
            LOGGER.info("Descubrimiento UDP escuchando en %s", self.PORT)
            while not self._stop.is_set():
                try:
                    request, address = self._socket.recvfrom(256)
                except socket.timeout:
                    continue
                if request.strip() == self.REQUEST:
                    self._socket.sendto(response, address)
        except Exception:
            LOGGER.exception("No se pudo iniciar el descubrimiento UDP")

    def stop(self):
        self._stop.set()
        if self._socket is not None:
            self._socket.close()
