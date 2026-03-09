import os
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
LOCAL_PORT = os.getenv("LOCAL_PORT")

def extraer_todo_futbol_libre():
    search_key = sys.argv[1].lower() if len(sys.argv) > 1 else None
    
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1440,900")
    options.add_argument("--headless")        # Sin ventana (obligatorio en server)
    options.add_argument("--no-sandbox")       # Para que no chille por ser root
    options.add_argument("--disable-dev-shm-usage") # Para no saturar la memoria del LXC
    driver = webdriver.Chrome(options=options)

    wait = WebDriverWait(driver, 20)

    try:
        driver.get(FUTBOL_LIBRE_URL)
        time.sleep(5) 

        # 1. JS modificado para capturar LOGO y separar TORNEO de PARTICIPANTES
        script_general = """
        let key = arguments[0];
        let listaEventos = document.querySelectorAll('#menu > li');
        let resultados = []; 
        
        listaEventos.forEach((li) => {
            let nombreSpan = li.querySelector('div span');
            let imgLogo = li.querySelector('div div img'); // Ruta del logo
            
            if (nombreSpan) {
                let nombreCompleto = nombreSpan.textContent.trim();
                let urlLogo = imgLogo ? imgLogo.src : "";
                
                if (key && !nombreCompleto.toLowerCase().includes(key)) {
                    return;
                }

                // 3. Separar por ":" (Torneo : Quien juega)
                let partes = nombreCompleto.split(':');
                let torneo = partes.length > 1 ? partes[0].trim() : "Otros";
                let participantes = partes.length > 1 ? partes[1].trim() : partes[0].trim();
                
                let links = li.querySelectorAll('ul a'); 
                let opciones = Array.from(links).map(a => {
                    let canalSpan = a.querySelector('span');
                    return {
                        url: a.href,
                        canal: canalSpan ? canalSpan.textContent.trim() : "Opción"
                    };
                });
                
                resultados.push({ 
                    participantes: participantes, 
                    torneo: torneo, 
                    logo: urlLogo, 
                    opciones: opciones 
                });
            }
        });
        return resultados;
        """
        todo_el_menu = driver.execute_script(script_general, search_key)

        if not todo_el_menu:
            print("No se encontraron eventos.")
            return

        print(f"Se encontraron {len(todo_el_menu)} eventos.")

        m3u_content = "#EXTM3U\n"

        for item in todo_el_menu:
            opciones = item['opciones']
            if not opciones:
                continue

            print(f"\n--- Procesando: {item['participantes']} ({item['torneo']}) ---")

            for opt in opciones:
                print(f"  > Extrayendo: {opt['canal']}...", end=" ", flush=True)
                
                try:
                    driver.get(opt['url'])
                    try:
                        wait_iframe = WebDriverWait(driver, 10) 
                        wait_iframe.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "embedIframe")))
                        time.sleep(3)

                        scripts = driver.find_elements(By.TAG_NAME, "script")
                        url_encontrada = False
                        
                        for script in scripts:
                            try:
                                contenido = script.get_attribute("innerHTML")
                                if contenido and ".m3u8?token=" in contenido:
                                    match = re.search(r'["\'](https?://.*?\.m3u8\?token=.*?)["\']', contenido)
                                    if match:
                                        url_final = match.group(1)
                                        
                                        # Formato solicitado: <quien juega>, <torneo> - <nombre canal>
                                        nombre_canal_formateado = f"{item['participantes']}, {item['torneo']} - {opt['canal']}"
                                        
                                        # Agregamos logo y Group Title: Sports
                                        m3u_content += f'#EXTINF:-1 tvg-logo="{item["logo"]}" group-title="Sports", {nombre_canal_formateado}\n{url_final}\n'
                                        
                                        url_encontrada = True
                                        break
                            except:
                                continue 
                        
                        if url_encontrada:
                            print("OK")
                        else:
                            print("No se encontró URL.")
                        
                        driver.switch_to.default_content()

                    except Exception:
                        print("Error en reproductor.")
                        try: driver.switch_to.default_content()
                        except: pass

                except Exception:
                    print("Error al cargar página.")
                    continue

        with open(M3U_FILE, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        
        print(f"\nArchivo '{M3U_FILE}' generado exitosamente.")

    finally:
        driver.quit()

if __name__ == "__main__":
    extraer_todo_futbol_libre()