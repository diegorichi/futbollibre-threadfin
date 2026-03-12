import xml.etree.ElementTree as ET
import re
import os
from flask import jsonify

XML_PATH = "/opt/threadfin/eventos.xml"

@app.route('/grilla', methods=['GET'])
def get_grilla():
    if not os.path.exists(XML_PATH):
        return jsonify([])
    
    try:
        tree = ET.parse(XML_PATH)
        root = tree.getroot()
        partidos = []

        # Diccionario para mapear ID de canal a Nombre (opcional si queres el nombre "Evento X")
        canales = {child.get('id'): child.find('display-name').text 
                   for child in root.findall('channel')}

        for prog in root.findall('programme'):
            titulo_raw = prog.find('title').text if prog.find('title') is not None else ""
            
            # 1. Filtrar "Slot Libre"
            if "Slot Libre" in titulo_raw:
                continue
            
            # 2. Limpiar el título y extraer la hora real
            # Buscamos el patrón [HH:MM] y el resto del texto
            match = re.search(r'\[(\d{2}:\d{2})\]\s*(.*)', titulo_raw)
            
            if match:
                hora_real = match.group(1)
                evento_limpio = match.group(2)
                
                # Quitar el prefijo "PROXIMAMENTE: " si existe
                evento_limpio = evento_limpio.replace("PROXIMAMENTE: ", "").strip()
                
                canal_id = prog.get('channel')
                nombre_canal = canales.get(canal_id, canal_id)

                partidos.append({
                    "hora": hora_real,
                    "evento": evento_limpio,
                    "canal": nombre_canal
                })

        # Ordenar por hora
        partidos.sort(key=lambda x: x['hora'])
        
        return jsonify(partidos)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500