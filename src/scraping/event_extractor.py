"""Detecta una estrategia y busca eventos en la página y sus iframes."""

from .eventos_html_strategy import EventosHtmlStrategy
from .agenda_php_strategy import AgendaPhpStrategy
from .direct_channel_strategy import DirectChannelStrategy
from .menu_strategy import MenuStrategy
from .structured_time_strategy import StructuredTimeStrategy
from .agenda_time_strategy import AgendaTimeStrategy
from .event_link_time_strategy import EventLinkTimeStrategy


STRATEGIES = (
    EventLinkTimeStrategy(),
    EventosHtmlStrategy(),
    AgendaPhpStrategy(),
    DirectChannelStrategy(),
    StructuredTimeStrategy(),
    AgendaTimeStrategy(),
    MenuStrategy(),
)


def _clave_evento(evento):
    opciones = tuple(opcion.get("url", "") for opcion in evento.get("opciones", []))
    return evento.get("nombre", ""), evento.get("hora", ""), opciones


def extraer_eventos(driver):
    """Busca eventos en todos los contextos y combina las estrategias válidas."""
    encontrados = []
    estrategia_usada = None

    def recorrer_contexto():
        nonlocal estrategia_usada

        for estrategia in STRATEGIES:
            eventos = estrategia.extraer(driver)
            if eventos:
                if estrategia_usada:
                    estrategia_usada += f", {estrategia.nombre}"
                else:
                    estrategia_usada = estrategia.nombre
                encontrados.extend(eventos)

        iframes = driver.find_elements("tag name", "iframe")
        for iframe in iframes:
            try:
                driver.switch_to.frame(iframe)
                recorrer_contexto()
                driver.switch_to.parent_frame()
            except Exception:
                driver.switch_to.default_content()

    recorrer_contexto()

    unicos = []
    vistos = set()
    for evento in encontrados:
        clave = _clave_evento(evento)
        if clave not in vistos:
            vistos.add(clave)
            unicos.append(evento)

    return unicos, estrategia_usada
