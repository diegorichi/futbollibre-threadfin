import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import unicodedata
import re
import time
import sys

load_dotenv()

FUTBOL_LIBRE_URL = os.getenv("FUTBOL_LIBRE_URL")
M3U_FILE = "eventos.m3u" #os.getenv("M3U_FILE")
THREADFIN_API_URL = os.getenv("THREADFIN_API_URL", "http://localhost:34400/api/")
SINTEL_URL = "https://demo.unified-streaming.com/k8s/live/scte35.isml/.m3u8"

def sanitizar_nombre(texto):
    if not texto:
        return ""
    # 1. Normalizar Unicode (convierte caracteres raros a su forma base)
    texto = unicodedata.normalize('NFKC', texto)

    # 2. Reemplazar saltos de línea, retornos y tabs por un espacio simple
    texto = re.sub(r'[\r\n\t]+', ' ', texto)
    # 3. Quitar espacios múltiples y dejar solo uno
    texto = re.sub(r'\s+', ' ', texto)

    # 4. Limpiar los bordes
    return texto.strip()

def es_proximo(hora_str):
    try:
        ahora = datetime.now()
        hora_obj = datetime.strptime(hora_str, "%H:%M").replace(
            year=ahora.year, month=ahora.month, day=ahora.day
        )
        # Eventos activos: desde hace 2.5 horas hasta 30 mins en el futuro
        return (ahora + timedelta(minutes=30)) <= hora_obj
    except:
        return False

def es_activo(hora_str):
    try:
        ahora = datetime.now()
        hora_obj = datetime.strptime(hora_str, "%H:%M").replace(
            year=ahora.year, month=ahora.month, day=ahora.day
        )
        # Eventos activos: desde hace 2.5 horas hasta 30 mins en el futuro
        return (ahora - timedelta(hours=2, minutes=30)) <= hora_obj <= (ahora + timedelta(minutes=30))
    except:
        return False

def generar_xmltv(eventos_mapeados, xml_path):
    ahora = datetime.now()
    inicio_str = ahora.strftime("%Y%m%d%H%M%S") + " -0300"
    # Le damos 3 horas de validez a cada programa en la guía
    fin_str = (ahora + timedelta(hours=3)).strftime("%Y%m%d%H%M%S") + " -0300"

    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']

    # Canales (E01-E30)
    for i in range(1, 31):
        xml_lines.append(f'  <channel id="E{i:02d}">')
        xml_lines.append(f'    <display-name>Evento {i}</display-name>')
        xml_lines.append(f'  </channel>')

    # Programas
    for ev in eventos_mapeados:
        try:
            # Parseamos la hora que viene del scraper (HH:MM)
            hora_evento = datetime.strptime(ev['hora_real'], "%H:%M").replace(
                year=ahora.year, month=ahora.month, day=ahora.day
            )
            
            # Si la hora del evento es mayor a la actual + 12hs, 
            # probablemente sea un error de casteo de día (ayer/mañana)
            if hora_evento > ahora + timedelta(hours=12):
                hora_evento -= timedelta(days=1)
                
            inicio_xml = hora_evento.strftime("%Y%m%d%H%M%S") + " -0300"
            # Timeout de 3 horas desde el inicio del evento
            fin_xml = (hora_evento + timedelta(hours=3)).strftime("%Y%m%d%H%M%S") + " -0300"
        except:
            # Fallback por si la hora falla
            inicio_xml = ahora.strftime("%Y%m%d%H%M%S") + " -0300"
            fin_xml = (ahora + timedelta(hours=2)).strftime("%Y%m%d%H%M%S") + " -0300"

        xml_lines.append(f'  <programme start="{inicio_xml}" stop="{fin_xml}" channel="{ev["slot"]}">')
        xml_lines.append(f'    <title lang="es">{ev["hora_real"]} {ev["nombre_guia"]} ({ev["canal"]})</title>')
        xml_lines.append(f'    <desc lang="es">Transmision en vivo: {ev["nombre_guia"]}</desc>')
        if ev.get('logo'):
            xml_lines.append(f'    <icon src="{ev["logo"]}" />')
        xml_lines.append(f'  </programme>')

    xml_lines.append('</tv>')

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))

def extraer_todo_futbol_libre():
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1440,900")
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        driver.get(FUTBOL_LIBRE_URL)
        print("levantando futbol libre y esperando 4 segundos")
        time.sleep(4)

        eventos_raw = driver.execute_script("""
            return Array.from(document.querySelectorAll('#menu > li')).map(li => ({
                nombre: li.querySelector('div span') ? li.querySelector('div span').textContent.trim() : "",
                hora: li.querySelector('div div time') ? li.querySelector('div div time').textContent.trim() : "00:00",
                logo: li.querySelector('div div img').src, // Ruta del logo
                opciones: Array.from(li.querySelectorAll('ul a')).map(a => ({
                    url: a.href,
                    canal: a.querySelector('span') ? a.querySelector('span').textContent.trim() : "Opción"
                }))
            }));
        """)
        print("eventos obtenidos")

        # 1. Separar los que estan EN VIVO de los que son PROXIMAMENTE
        en_vivo = []
        proximos = []
        
        for ev in eventos_raw:
            if es_activo(ev['hora']):
                for opt in ev['opciones']:
                    en_vivo.append({'nombre': ev['nombre'], 'hora': ev['hora'], 'canal': opt['canal'], 'logo': ev['logo'], 'url': opt['url']})
            else:
                if (es_proximo(ev['hora'])):
                    # Guardamos los proximos para rellenar si sobran slots
                    proximos.append(ev)

        m3u_content = "#EXTM3U\n"
        datos_para_xml = []

        print("Armando canales y extrayendo info")

        # 2. Iterar las 30 veces obligatorias
        for i in range(1, 31):
            slot_id = f"E{i:02d}"
            logo = ""

            if len(en_vivo) > 0:
                # Ocupar slot con evento en vivo
                item = en_vivo.pop(0)
                nombre = sanitizar_nombre(item['nombre'])
                logo = item['logo']
                print(f"Slot {slot_id}: {item['hora']} {nombre} ({item['canal']})")
                datos_para_xml.append({'slot': slot_id, 'nombre_guia': nombre, 'logo': logo, 'hora_real': item['hora'], 'canal': item['canal']})

                try:
                    driver.get(item['url'])
                    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "embedIframe")))
                    time.sleep(2)
                    match = re.search(r'["\'](https?://.*?\.m3u8\?token=.*?)["\']', driver.page_source)
                    
                    if match:
                        link_stream = match.group(1)
                        nombre_txt = f"[{item['hora']}] {nombre} - {item['canal']}"
                    else:
                        link_stream = SINTEL_URL
                        nombre_txt = f"[{item['hora']}] {nombre} (Link no encontrado)"
                except:
                    link_stream = SINTEL_URL
                    nombre_txt = f"[{item['hora']}] {nombre} (Error de carga)"
                
                driver.switch_to.default_content()
            else:
                # Rellenar con "Próximamente"
                if len(proximos) > 0:
                    px = proximos.pop(0)
                    nombre = sanitizar_nombre(px['nombre'])

                    nombre_txt = f"PROXIMAMENTE: [{px['hora']}] {nombre}"
                else:
                    nombre_txt = "Slot Libre - Sin Eventos"
                logo = px['logo']
                datos_para_xml.append({'slot': slot_id, 'nombre_guia': nombre_txt, 'logo': logo, 'hora_real': px['hora'], 'canal': "")


                link_stream = SINTEL_URL
                print(f"Slot {slot_id}: {nombre_txt}")
            # Escribir el canal al M3U (siempre con el mismo tvg-id para la tele)
            m3u_content += f'#EXTINF:-1 tvg-id="{slot_id}" tvg-name="Evento {i}" tvg-logo="{logo}" group-title="Sports",{nombre_txt}\n'
            m3u_content += f'#EXTVLCOPT:http-user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"\n'
            m3u_content += f'{link_stream}\n'
            
            XML_FILE = M3U_FILE.replace(".m3u", ".xml")
            # Guardamos para el XML

            generar_xmltv(datos_para_xml, XML_FILE)

        # 3. Guardar y Notificar
        with open(M3U_FILE, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        
        comandos = [
            {"cmd": "update.m3u"},
            {"cmd": "update.xmltv"},
            {"cmd": "update.xepg"}
        ]
        
        for payload in comandos:
            try:
                response = requests.post(f"{THREADFIN_API_URL}", json=payload)
                if response.status_code == 200:
                    print(f"[Threadfin] OK: Comando {payload['cmd']} aceptado.")
                elif response.status_code == 423:
                    print(f"[Threadfin] El servidor esta bloqueado (423). Esperando 5 segundos...")
                else:
                    print(f"[Threadfin] Error {response.status_code}: {response.text}")

            except Exception as e:
                print(f"[Threadfin] Error de conexion: {e}")
            time.sleep(2)
            
        print("\nGrilla de 30 canales actualizada en Threadfin.")

    finally:
        driver.quit()

if __name__ == "__main__":
    extraer_todo_futbol_libre()