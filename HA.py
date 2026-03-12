import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# Configuración HA
HA_URL = "http://IP_DE_TU_HA:8123/api/states/sensor.agenda_futbol"
HA_TOKEN = os.getenv("HA_TOKEN") # Crealo en HA: Perfil -> Tokens de acceso de larga duración

def enviar_a_home_assistant(eventos):
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "content-type": "application/json",
    }
    
    # El 'state' será la cantidad de partidos, los 'attributes' la grilla completa
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
        print("✅ Enviado a Home Assistant")
    else:
        print(f"❌ Error HA: {response.text}")

# ... (Al final de tu lógica de parseo cuando ya tenés la lista 'eventos_finales')
enviar_a_home_assistant(eventos_finales)