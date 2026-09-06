"""Agrupa eventos iguales publicados por sitios con pequeñas diferencias."""

from copy import deepcopy
from difflib import SequenceMatcher
import re
import unicodedata


def normalizar_nombre(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    texto = texto.lower().replace("&", " y ")
    texto = re.sub(r"\b(vs?\.?|contra)\b", " vs ", texto)
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def _equipos(nombre):
    nombre = normalizar_nombre(nombre)
    if ":" in nombre:
        nombre = nombre.rsplit(":", 1)[-1].strip()
    partes = re.split(r"\bvs\b", nombre, maxsplit=1)
    return tuple(parte.strip() for parte in partes) if len(partes) == 2 else (nombre,)


def eventos_equivalentes(izquierdo, derecho):
    hora_izquierda = izquierdo.get("hora", "")
    hora_derecha = derecho.get("hora", "")
    if hora_izquierda and hora_derecha and hora_izquierda != hora_derecha:
        return False

    equipos_izquierda = _equipos(izquierdo.get("nombre", ""))
    equipos_derecha = _equipos(derecho.get("nombre", ""))
    if equipos_izquierda == equipos_derecha:
        return True

    nombre_izquierdo = " vs ".join(equipos_izquierda)
    nombre_derecho = " vs ".join(equipos_derecha)
    return SequenceMatcher(None, nombre_izquierdo, nombre_derecho).ratio() >= 0.86


def agrupar_eventos(eventos):
    grupos = []
    for evento in eventos:
        grupo = next((grupo for grupo in grupos if eventos_equivalentes(grupo, evento)), None)
        if grupo is None:
            grupo = deepcopy(evento)
            grupo["fuentes"] = list(evento.get("fuentes", []))
            grupo["opciones"] = []
            grupos.append(grupo)

        for fuente in evento.get("fuentes", []):
            if fuente not in grupo["fuentes"]:
                grupo["fuentes"].append(fuente)
        urls_existentes = {opcion.get("url") for opcion in grupo["opciones"]}
        for opcion in evento.get("opciones", []):
            if opcion.get("url") not in urls_existentes:
                grupo["opciones"].append(deepcopy(opcion))
                urls_existentes.add(opcion.get("url"))
    return grupos
