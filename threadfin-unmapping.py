from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# --- CONFIGURACIÓN ---
THREADFIN_URL = "http://192.168.0.149:34400/web/"

def limpiar_mapping_futbol():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")        # Sin ventana (obligatorio en server)
    options.add_argument("--no-sandbox")       # Para que no chille por ser root
    options.add_argument("--disable-dev-shm-usage") # Para no saturar la memoria del LXC
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    
    try:
        print("Iniciando limpieza de mapping (FUTBOL_LIBRE)...")
        driver.get(THREADFIN_URL)
        wait = WebDriverWait(driver, 10)
        time.sleep(1)

        # 1. Clic en Mapping (li[4])
        mapping_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/nav/div/div/ul[1]/li[4]")))
        time.sleep(1)
        mapping_tab.click()

        # 2. Clic en Bulk Edit
        time.sleep(1)
        bulk_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[4]/div[1]/div/div/div[1]/input[2]")))
        bulk_btn.click()

        # 3. Analizar la Tabla 1 (Mapeados)
        time.sleep(2) # Esperamos que cargue bien la tabla 1
        wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/div[1]/div/div/div[2]/table[1]")))
        
        filas = driver.find_elements(By.XPATH, "/html/body/div[4]/div[1]/div/div/div[2]/table[1]/tr")
        print(f"Filas encontradas en tabla de activos: {len(filas)}")

        primer_indice_futbol = None

        for i in range(1, len(filas) + 1):
            base_xpath = f"/html/body/div[4]/div[1]/div/div/div[2]/table[1]/tr[{i}]"
            try:
                # Buscamos el texto FUTBOL_LIBRE en la columna 5
                fuente_elem = driver.find_element(By.XPATH, f"{base_xpath}/td[5]/p")
                fuente_text = fuente_elem.text
                
                if "FUTBOL_LIBRE" in fuente_text:
                    if primer_indice_futbol is None:
                        primer_indice_futbol = i
                    
                    # Clic en checkbox de la fila
                    checkbox = driver.find_element(By.XPATH, f"{base_xpath}/td[1]/input")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                    time.sleep(2) # Delay de 2 segundos como pediste
                    
                    if not checkbox.is_selected():
                        checkbox.click()
                        print(f"Marcado para borrar canal en fila {i}")

            except Exception:
                continue

        # 4. Abrir popup sobre el texto del primero encontrado para Desactivar
        if primer_indice_futbol:
            print(f"Abriendo popup de limpieza (Fila {primer_indice_futbol})...")
            time.sleep(1)
            # Clic sobre el mismo <p> que contiene FUTBOL_LIBRE
            btn_popup = driver.find_element(By.XPATH, f"/html/body/div[4]/div[1]/div/div/div[2]/table[1]/tr[{primer_indice_futbol}]/td[5]/p")
            btn_popup.click()

            # Popup: Desactivar (mismo input que antes según tu Xpath)
            time.sleep(1)
            input_desactivar = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div/div[2]/div/div/div/table/tr[2]/td[2]/input")))
            input_desactivar.click()
            
            # Botón Done
            time.sleep(1)
            btn_done = driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div[2]/div/div/div/div/input[4]")
            btn_done.click()
            print("Mapping desactivado para todos los seleccionados.")
        else:
            print("No se encontraron canales de FUTBOL_LIBRE para borrar.")

        # 5. Guardar Cambios Finales
        print("Guardando cambios globales...")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        btn_save_final = driver.find_element(By.XPATH, "/html/body/div[4]/div[1]/div/div/div[1]/input[1]")
        driver.execute_script("arguments[0].click();", btn_save_final)
        
        print("Esperando 10 segundos para persistencia en disco...")
        time.sleep(10) 
        print("Limpieza completada.")

    except Exception as e:
        print(f"Error durante la limpieza: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    limpiar_mapping_futbol()