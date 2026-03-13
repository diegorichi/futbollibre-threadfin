import xml.etree.ElementTree as ET
import requests
import re
import json
import os
from dotenv import load_dotenv

load_dotenv()

XML_FILE = os.getenv("XML_FILE")
NTFY_URL = os.getenv("NTFY_URL")
JSON_FILE = os.getenv("JSON_FILE")
KEYS = [k.strip().lower() for k in os.getenv("KEYS", "").split(",") if k]

HA_URL = os.getenv("HA_URL")
HA_TOKEN = os.getenv("HA_TOKEN")

def enviar_a_home_assistant(eventos):
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "content-type": "application/json",
    }
    
    payload = {
        "state": len(eventos),
        "attributes": {
            "eventos": eventos,
            "friendly_name": "Agenda de Fútbol",
            "icon": "mdi:soccer"
        }
    }
    
    response = requests.post(HA_URL, headers=headers, json=payload)
    if response.status_code in [200, 201]:
        print("-> Enviado a Home Assistant")
    else:
        print(f"-> Error HA: {response.text}")

def agrupar_eventos(eventos_sucios):
    agrupados = {}

    for ev in eventos_sucios:
        # Usamos Hora + Equipos como llave para identificar el mismo partido
        id_evento = f"{ev['hora']}_{ev['equipos']}"
        print(id_evento)
        # Limpiamos el canal (solo lo que está antes del |)
        #canal_limpio = ev['canal'].split('|')[0].strip()

        if id_evento not in agrupados:
            # Si es la primera vez que vemos el partido, lo guardamos
            # ev['canal'] = [canal_limpio]
            agrupados[id_evento] = ev
        #else:
            # Si ya existe, solo agregamos el canal si no está repetido
            #if canal_limpio not in agrupados[id_evento]['canales']:
            #    agrupados[id_evento]['canales'].append(canal_limpio)

    # Re-formateamos para el envío final
    lista_final = []
    for item in agrupados.values():
        #item['canal'] = ", ".join(item['canales']) # "ESPN, TV Pública, Disney+"
        #del item['canales'] # Limpiamos la lista temporal
        lista_final.append(item)
    
    # Ordenamos por hora para que en HA y ntfy quede prolijo
    return sorted(lista_final, key=lambda x: x['hora'])

def procesar_y_notificar():
    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    agenda_match = []
    agenda_json = []

    tiene_filtro = isinstance(KEYS, list) and len(KEYS) > 0

    for programme in root.findall('programme'):
        title_elem = programme.find("title")
        if title_elem is None or not title_elem.text:
            continue
            
        title_text = title_elem.text
        title_lower = title_text.lower()
        # Si machea con alguna key

        if any(key in title_lower for key in KEYS) or not tiene_filtro:
            print(f"{title_text}")
            # Regex para capturar: Hora, Torneo, Equipos y opcionalmente el Canal
            # Explicación: 
            # \[(?P<hora>\d{2}:\d{2})\] -> Captura la hora entre corchetes
            # \s*(?P<torneo>.*?):\s* -> Captura el torneo hasta los dos puntos
            # (?P<equipos>.*?)          -> Captura los equipos
            # (\s*-\s*(?P<canal>.*))?$  -> Si existe un guion al final, captura el canal
            pattern = r"\[(?P<hora>\d{2}:\d{2})\]\s*(?P<torneo>.*?):\s*(?P<equipos>.*?)(?:\s*-\s*(?P<canal>[^|]*))?$"

            match = re.search(pattern, title_text)

            if match:
                hora = match.group("hora")
                torneo = match.group("torneo")
                equipos = match.group("equipos").strip()
                # Limpiamos el canal si tiene el sufijo "| OPX"
                canal_raw = match.group("canal")
                canal = canal_raw.split("|")[0].strip() if canal_raw else ""
                agenda_json.append({
                    "hora": hora,
                    "torneo": torneo,
                    "equipos": equipos,
                    "canal": canal
                })

    agenda_json = agrupar_eventos(agenda_json)

    for ev in agenda_json:
        info_evento = f"{ev['hora']} | {ev['equipos']}"
        agenda_match.append(info_evento)

    # Enviar a ntfy si hay resultados
    if agenda_match:
        mensaje = "\n".join(agenda_match)
        requests.post(NTFY_URL, 
                      data=mensaje.encode('utf-8'), 
                      headers={"Title": "Grilla Deportiva"})

        agenda_json.sort(key=lambda x: x['hora'])
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump({"eventos": agenda_json}, f, ensure_ascii=False, indent=4)

        #enviar_a_home_assistant(agenda_json)

if __name__ == "__main__":
    procesar_y_notificar()