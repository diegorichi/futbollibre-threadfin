import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import time
import sys

load_dotenv()

FUTBOL_LIBRE_URL = os.getenv("FUTBOL_LIBRE_URL")
M3U_FILE = os.getenv("M3U_FILE")
THREADFIN_URL = os.getenv("THREADFIN_URL", "http://localhost:34400/api/")
SINTEL_URL = "https://demo.unified-streaming.com/k8s/live/scte35.isml/.m3u8"

def es_horario_valido(hora_str):
    try:
        ahora = datetime.now()
        hora_obj = datetime.strptime(hora_str, "%H:%M").replace(
            year=ahora.year, month=ahora.month, day=ahora.day
        )
        # Eventos activos: desde hace 2.5 horas hasta 5 mins en el futuro
        return (ahora - timedelta(hours=2, minutes=30)) <= hora_obj <= (ahora + timedelta(minutes=30))
    except:
        return False

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
        time.sleep(4) 

        eventos_raw = driver.execute_script("""
            return Array.from(document.querySelectorAll('#menu > li')).map(li => ({
                nombre: li.querySelector('div span') ? li.querySelector('div span').textContent.trim() : "",
                hora: li.querySelector('div div time') ? li.querySelector('div div time').textContent.trim() : "00:00",
                opciones: Array.from(li.querySelectorAll('ul a')).map(a => ({
                    url: a.href,
                    canal: a.querySelector('span') ? a.querySelector('span').textContent.trim() : "Opción"
                }))
            }));
        """)
        
        # 1. Separar los que estan EN VIVO de los que son PROXIMAMENTE
        en_vivo = []
        proximos = []
        
        for ev in eventos_raw:
            if es_horario_valido(ev['hora']):
                for opt in ev['opciones']:
                    en_vivo.append({'nombre': ev['nombre'], 'hora': ev['hora'], 'canal': opt['canal'], 'url': opt['url']})
            else:
                # Guardamos los proximos para rellenar si sobran slots
                proximos.append(ev)

        m3u_content = "#EXTM3U\n"
        
        # 2. Iterar las 15 veces obligatorias
        for i in range(1, 16):
            slot_id = f"E{i:02d}"
            
            if len(en_vivo) > 0:
                # Ocupar slot con evento en vivo
                item = en_vivo.pop(0)
                print(f"Slot {slot_id}: {item['nombre']} ({item['canal']})")
                
                try:
                    driver.get(item['url'])
                    wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "embedIframe")))
                    time.sleep(2)
                    match = re.search(r'["\'](https?://.*?\.m3u8\?token=.*?)["\']', driver.page_source)
                    
                    if match:
                        link_stream = match.group(1)
                        nombre_txt = f"[{item['hora']}] {item['nombre']} - {item['canal']}"
                    else:
                        link_stream = SINTEL_URL
                        nombre_txt = f"[{item['hora']}] {item['nombre']} (Link no encontrado)"
                except:
                    link_stream = SINTEL_URL
                    nombre_txt = f"[{item['hora']}] {item['nombre']} (Error de carga)"
                
                driver.switch_to.default_content()
            else:
                # Rellenar con "Próximamente"
                if len(proximos) > 0:
                    px = proximos.pop(0)
                    nombre_txt = f"PROXIMAMENTE: [{px['hora']}] {px['nombre']}"
                else:
                    nombre_txt = "Slot Libre - Sin Eventos"
                
                link_stream = SINTEL_URL
                print(f"Slot {slot_id}: {nombre_txt}")

            # Escribir el canal al M3U (siempre con el mismo tvg-id para la tele)
            m3u_content += f'#EXTINF:-1 tvg-id="{slot_id}" tvg-name="Evento {i}" group-title="EVENTOS", {nombre_txt}\n'
            m3u_content += f'#EXTVLCOPT:http-user-agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"\n'
            m3u_content += f'{link_stream}\n'

        # 3. Guardar y Notificar
        with open(M3U_FILE, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        
        requests.post(THREADFIN_URL, json={"cmd": "update.m3u"})
        #os.system("pkill -9 ffmpeg")
        print("\nGrilla de 15 canales actualizada en Threadfin.")

    finally:
        driver.quit()

if __name__ == "__main__":
    extraer_todo_futbol_libre()