"""Recorrido de múltiples sitios y combinación de sus eventos."""

from .event_extractor import extraer_eventos
from .event_matching import agrupar_eventos


def extraer_eventos_de_sitios(driver, urls):
    eventos = []
    sitios_ok = []
    errores = []

    for url in urls:
        try:
            driver.switch_to.default_content()
            driver.get(url)
            encontrados, estrategia = extraer_eventos(driver)
            for evento in encontrados:
                evento["fuentes"] = [url]
                for opcion in evento.get("opciones", []):
                    opcion["fuente"] = url
                eventos.append(evento)
            sitios_ok.append({"url": url, "estrategia": estrategia, "eventos": len(encontrados)})
        except Exception as error:
            errores.append({"url": url, "error": str(error)})

    driver.switch_to.default_content()
    return agrupar_eventos(eventos), sitios_ok, errores
