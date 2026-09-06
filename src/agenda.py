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

        id_evento = f"{ev['hora']}_{ev['equipos']}"
        if id_evento not in agrupados:
            agrupados[id_evento] = ev

    lista_final = []
    for item in agrupados.values():
        lista_final.append(item)
    
    return sorted(lista_final, key=lambda x: x['hora'])

def procesar_y_notificar():
    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    agenda_match = []
    agenda_json = []

    tiene_filtro = isinstance(KEYS, list) and len(KEYS) > 0
    print("iniciando parser")
    for programme in root.findall('programme'):
        title_elem = programme.find("title")
        if title_elem is None or not title_elem.text:
            continue
            
        title_text = title_elem.text.replace("PROXIMAMENTE: ", "")
        title_lower = title_text.lower()

        if any(key in title_lower for key in KEYS) or not tiene_filtro:
            # Regex para capturar: Hora, Torneo, Equipos y opcionalmente el Canal
            pattern = r"\[(?P<hora>\d{2}:\d{2})\]\s*(?P<torneo>.*?):\s*(?P<equipos>[^;]+)(?:\s*;\s*(?P<canal>[^|]*))?"
            
            match = re.search(pattern, title_text)

            if match:
                hora = match.group("hora")
                torneo = match.group("torneo")
                equipos = match.group("equipos").strip()
                # Limpiamos el canal si tiene el sufijo "| OPX"
                canal = match.group("canal")

                agenda_json.append({
                    "hora": hora,
                    "torneo": torneo,
                    "equipos": equipos,
                    "canal": canal
                })

    print("agrupando y ordenando eventos")

    agenda_json = agrupar_eventos(agenda_json)
    agenda_json.sort(key=lambda x: x['hora'])

    for ev in agenda_json:
        info_evento = f"{ev['hora']} | {ev['equipos']}"
        agenda_match.append(info_evento)

    # Enviar a ntfy si hay resultados
    if agenda_match:
        print("Enviando a NTFY")

        mensaje = "\n".join(agenda_match)
        requests.post(NTFY_URL, 
                      data=mensaje.encode('utf-8'), 
                      headers={"Title": "Grilla Deportiva"})

        print("Enviando a HomeAssistant")
        with open(JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump({"eventos": agenda_json}, f, ensure_ascii=False, indent=4)

        enviar_a_home_assistant(agenda_json)

if __name__ == "__main__":
    procesar_y_notificar()