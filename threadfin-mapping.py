from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# --- CONFIGURACIÓN ---
THREADFIN_URL = "http://192.168.0.149:34400/web/"

def realizar_mapping_bulk():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")        # Sin ventana (obligatorio en server)
    options.add_argument("--no-sandbox")       # Para que no chille por ser root
    options.add_argument("--disable-dev-shm-usage") # Para no saturar la memoria del LXC
    driver = webdriver.Chrome(options=options)

    try:
        print("Iniciando secuencia Bulk Mapping...")
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

        # 3. Analizar la tabla y marcar Checkboxes
        time.sleep(1)
        wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/div[1]/div/div/div[2]/table[2]")))
        
        filas = driver.find_elements(By.XPATH, "/html/body/div[4]/div[1]/div/div/div[2]/table[2]/tr")
        print(f"Filas encontradas: {len(filas)}")

        primer_indice_futbol = None

        for i in range(1, len(filas) + 1):
            base_xpath = f"/html/body/div[4]/div[1]/div/div/div[2]/table[2]/tr[{i}]"
            try:
                fuente_text = driver.find_element(By.XPATH, f"{base_xpath}/td[5]/p").text
                
                if "FUTBOL_LIBRE" in fuente_text:
                    # Si es el primero, lo guardamos para el popup final
                    if primer_indice_futbol is None:
                        primer_indice_futbol = i
                        print(f"Primer canal encontrado en fila {i}. Se usará para propagar.")
                    
                    # CORRECCIÓN: El clic se hace SIEMPRE que sea FUTBOL_LIBRE
                    checkbox = driver.find_element(By.XPATH, f"{base_xpath}/td[1]/input")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", checkbox)
                    time.sleep(2)
                    
                    if not checkbox.is_selected(): # Evita desmarcar si ya estaba marcado
                        checkbox.click()
                        print(f"Marcado canal {i}")

            except Exception as e:
                print(f"Error procesando bulk: {e}")
                continue
        
        # 4. Editar solo el primero encontrado para propagar cambios
        if primer_indice_futbol:
            print(f"Abriendo edición del primer canal (Fila {primer_indice_futbol})...")
            time.sleep(1)
            celda_3 = driver.find_element(By.XPATH, f"/html/body/div[4]/div[1]/div/div/div[2]/table[2]/tr[{primer_indice_futbol}]/td[3]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", celda_3)
            time.sleep(2)
            celda_3.click()

            # Popup: Activar y Confirmar
            time.sleep(1)
            input_popup = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[2]/div/div/div[2]/div/div/div/table/tr[2]/td[2]/input")))
            input_popup.click()
            
            time.sleep(1)
            btn_confirm = driver.find_element(By.XPATH, "/html/body/div[2]/div/div/div[2]/div/div/div/div/input[4]")
            btn_confirm.click()
            print("Configuración propagada a todos los seleccionados.")
        else:
            print("No se encontraron canales de FUTBOL_LIBRE.")

        # 5. Guardar cambios finales
        print("Guardando cambios globales...")
        time.sleep(2)
        
        # Volver arriba y clickear Save
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)
        btn_save_final = driver.find_element(By.XPATH, "/html/body/div[4]/div[1]/div/div/div[1]/input[1]")
        driver.execute_script("arguments[0].click();", btn_save_final)
        
        print("Esperando 10 segundos para asegurar el guardado en el host...")
        time.sleep(10) 
        print("¡Proceso terminado!")

    except Exception as e:
        print(f"Error durante la ejecución: {e}")
    
    #finally:
        #driver.quit()

if __name__ == "__main__":
    realizar_mapping_bulk()