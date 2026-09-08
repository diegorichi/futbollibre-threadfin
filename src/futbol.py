import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv, set_key
from selenium.common.exceptions import WebDriverException
import unicodedata
import re
import time
from scraping import extraer_eventos
from scraping.browser_driver import USER_AGENT, crear_driver
from scraping.site_scraper import extraer_eventos_de_sitios
from scraping.stream_extractor import StreamExtractionPool

ENV_FILE = os.getenv("ENV_FILE", ".env")
load_dotenv(ENV_FILE)

FUTBOL_LIBRE_URL = os.getenv("FUTBOL_LIBRE_URL")
M3U_FILE = os.getenv("M3U_FILE")
THREADFIN_API_URL = os.getenv("THREADFIN_API_URL", "http://localhost:34400/api/")
NTFY_URL = os.getenv("NTFY_URL")
SINTEL_URL = "https://demo.unified-streaming.com/k8s/live/scte35.isml/.m3u8"
PARALLEL_STREAM_EXTRACTION = os.getenv("PARALLEL_STREAM_EXTRACTION", "0").lower() in {"1", "true", "yes", "on"}
STREAM_EXTRACTION_WORKERS = max(1, int(os.getenv("STREAM_EXTRACTION_WORKERS", "4")))
MAX_CHANNELS = 100


def pagina_no_disponible(driver):
    title = (driver.title or "").lower()
    source = (driver.page_source or "")[:10000].lower()
    markers = (
        "404",
        "not found",
        "page not found",
        "site not found",
        "sitio no disponible",
    )
    return not title or any(marker in title or marker in source for marker in markers)


def actualizar_urls_y_notificar(urls_validas, urls_invalidas):
    borradas = 0
    if urls_invalidas and urls_validas:
        set_key(ENV_FILE, "FUTBOL_LIBRE_URL", ",".join(urls_validas))
        borradas = len(urls_invalidas)
        print(f"URLs eliminadas del .env: {borradas}")
    elif urls_invalidas:
        print("No se eliminan URLs: no quedó ningún sitio válido.")

    mensaje = (
        "Actualización de sitios FUTBOL_LIBRE_URL\n"
        f"Sitios válidos: {len(urls_validas)}\n"
        f"Sitios borrados: {borradas}"
    )
    if urls_invalidas:
        mensaje += "\nURLs detectadas como inválidas:\n" + "\n".join(urls_invalidas)

    if NTFY_URL:
        try:
            response = requests.post(
                NTFY_URL,
                data=mensaje.encode("utf-8"),
                headers={"Title": "Actualizar URLs de Fútbol Libre"},
                timeout=30,
            )
            response.raise_for_status()
            print("Aviso de URLs enviado a NTFY")
        except requests.RequestException as error:
            print(f"No se pudo enviar el aviso a NTFY: {error}")
    else:
        print("NTFY_URL no configurada; no se envió aviso.")

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
        return (ahora + timedelta(minutes=30)) <= hora_obj or hora_str == "23:59"
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

    # Canales (E01-E100)
    for i in range(1, MAX_CHANNELS + 1):
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
        xml_lines.append(f'    <title lang="es">{ev["nombre_guia"]}</title>')
        xml_lines.append(f'    <desc lang="es">{ev["nombre_guia"]}</desc>')
        if ev.get('logo'):
            xml_lines.append(f'    <icon src="{ev["logo"]}" />')
        xml_lines.append(f'  </programme>')

    xml_lines.append('</tv>')

    with open(xml_path, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))

def extraer_todo_futbol_libre():
    driver = crear_driver()
    stream_pool = None

    try:

        urls_to_try = [url.strip() for url in FUTBOL_LIBRE_URL.split(",") if url.strip()]

        urls_validas = []
        urls_invalidas = []
        for url in urls_to_try:
            try:
                print(f"Probando dominio: {url}...")
                driver.get(url)
                if pagina_no_disponible(driver):
                    raise WebDriverException("Dominio activo pero sin contenido válido")
                print(f"¡Éxito! Conectado a {url}")
                urls_validas.append(url)
            except WebDriverException as e:
                urls_invalidas.append(url)
                print(f"Fallo en {url}: {e.msg if hasattr(e, 'msg') else 'Error de conexión'}")
            except Exception as error:
                urls_invalidas.append(url)
                print(f"Fallo inesperado en {url}: {type(error).__name__}: {error}")

        actualizar_urls_y_notificar(urls_validas, urls_invalidas)

        if not urls_validas:
            print("Ningún dominio de la lista está operativo. Revisar el .env.")
            driver.quit()
            exit(1)
        
        print("Esperando unos segundos para asentar la carga de la página...")
        time.sleep(5)
        
        eventos_raw, sitios_ok, errores_sitios = extraer_eventos_de_sitios(driver, urls_validas)
        total_eventos_extraidos = sum(sitio["eventos"] for sitio in sitios_ok)
        print(f"Eventos detectados sin filtros: {total_eventos_extraidos}")
        print(f"Eventos únicos después de agrupar sitios: {len(eventos_raw)}")
        for sitio in sitios_ok:
            print(f"  {sitio['url']}: {sitio['eventos']} eventos")
        if not eventos_raw:
            print("ADVERTENCIA: No se pudieron obtener los eventos ni en la página ni en los iframes.")
        for error in errores_sitios:
            print(f"Error en {error['url']}: {error['error']}")

        # 1. Separar los que estan EN VIVO de los que son PROXIMAMENTE
        en_vivo = []
        proximos = []
        
        for ev in eventos_raw:
            ev['nombre'] = sanitizar_nombre(ev['nombre'])
            if ev['hora'] == '00:00': 
                ev['hora'] = '23:59'
            if es_activo(ev['hora']):
                for opt in ev['opciones']:
                    en_vivo.append({'nombre': ev['nombre'], 'hora': ev['hora'], 'canal': opt['canal'], 'logo': ev['logo'], 'url': opt['url']})
            else:
                if (es_proximo(ev['hora'])):
                    # Guardamos los proximos para rellenar si sobran slots
                    proximos.append(ev)
                else:
                    print(f"ignored: {ev}")

        stream_pool = StreamExtractionPool(
            driver,
            paralelo=PARALLEL_STREAM_EXTRACTION,
            workers=STREAM_EXTRACTION_WORKERS,
        )
        for item in en_vivo:
            stream_pool.submit(item["url"])
        if PARALLEL_STREAM_EXTRACTION:
            print(f"Seguimiento paralelo activado: {STREAM_EXTRACTION_WORKERS} workers.")

        resultados_stream = {}
        for item in en_vivo:
            if item["url"] not in resultados_stream:
                try:
                    resultados_stream[item["url"]] = stream_pool.result(item["url"])
                except Exception as error:
                    print(f"[Stream] Error en {item['url']}: {type(error).__name__}: {error}")
                    resultados_stream[item["url"]] = (None, None)

        streams_antes_del_filtro = len(en_vivo)
        en_vivo = [
            item for item in en_vivo
            if resultados_stream[item["url"]][0]
        ]
        streams_sin_resultado = streams_antes_del_filtro - len(en_vivo)
        print(f"Streams candidatos activos: {streams_antes_del_filtro}")
        print(f"Streams válidos encontrados: {len(en_vivo)}")
        print(f"Streams descartados por falta de URL: {streams_sin_resultado}")
        if len(en_vivo) > MAX_CHANNELS:
            print(f"ADVERTENCIA: {len(en_vivo) - MAX_CHANNELS} streams válidos quedan fuera de los {MAX_CHANNELS} slots.")
        print(f"Streams que entran en los slots actuales: {min(len(en_vivo), MAX_CHANNELS)}")

        m3u_content = "#EXTM3U\n"
        datos_para_xml = []
        eventos_descartados_sin_stream = 0
        streams_finales = 0

        print("Armando canales y extrayendo info")

        # 2. Iterar las 100 veces obligatorias
        for i in range(1, MAX_CHANNELS + 1):
            slot_id = f"E{i:02d}"
            logo = ""

            if len(en_vivo) > 0:
                # Ocupar slot con evento en vivo
                item = en_vivo.pop(0)
                streams_finales += 1
                logo = item['logo']
                hora_inicio_evento = item['hora']
                evento_descartado = False

                try:
                    print(f"buscando m3u de: {item['nombre']}, {item['url']}")
                    link_stream, origen = stream_pool.result(item['url'])
                    if link_stream:
                        print(f"Stream encontrado vía {origen}: {link_stream}")
                        nombre_txt = f"[{hora_inicio_evento}] {item['nombre']} ; {item['canal']}"
                    else:
                        evento_descartado = True
                        eventos_descartados_sin_stream += 1
                        link_stream = SINTEL_URL
                        nombre_txt = "Slot Libre - Sin Eventos"
                except Exception as error:
                    print(f"[Stream] Error en {item['url']}: {type(error).__name__}: {error}")
                    evento_descartado = True
                    eventos_descartados_sin_stream += 1
                    link_stream = SINTEL_URL
                    nombre_txt = "Slot Libre - Sin Eventos"
                
                print(nombre_txt)
                if evento_descartado:
                    logo = ""
                    hora_real = (datetime.now() - timedelta(minutes=5)).strftime("%H:%M")
                else:
                    # Parseamos la hora que viene del scraper (HH:MM)
                    ahora = datetime.now()
                    hora_real = datetime.strptime(hora_inicio_evento, "%H:%M").replace(
                        year=ahora.year, month=ahora.month, day=ahora.day
                    )
                    if (hora_real > ahora):
                        hora_real = (ahora - timedelta(minutes=5)).strftime("%H:%M")

                datos_para_xml.append({'slot': slot_id, 'nombre_guia': nombre_txt, 'logo': logo, 'hora_real': hora_real})

                try:
                    driver.switch_to.default_content()
                except WebDriverException as error:
                    print(f"[Chrome] Sesión no disponible: {error}")
            else:
                # Rellenar con "Proximamente"
                logo = ""
                if len(proximos) > 0:
                    px = proximos.pop(0)
                    logo = px['logo']
                    nombre_txt = f"PROXIMAMENTE: [{px['hora']}] {px['nombre']}"
                else:
                    nombre_txt = "Slot Libre - Sin Eventos"
                hora_inicio_proximo = (datetime.now() - timedelta(minutes=5)).strftime("%H:%M")
                datos_para_xml.append({'slot': slot_id, 'nombre_guia': nombre_txt, 'logo': logo, 'hora_real': hora_inicio_proximo})
                link_stream = SINTEL_URL
            
            # Escribir el canal al M3U (siempre con el mismo tvg-id para la tele)
            logo = "https://play-lh.googleusercontent.com/zRe9-Loct_wdUL8uuWMFqElFPhlsLDWYNemkyYNLWdQZhIWQPoWSQ_6o7wzBWB2Y6A=w600-h300-pc0xffffff-pd"

            m3u_content += f'#EXTINF:-1 tvg-id="{slot_id}" tvg-name="Deporte {i}" tvg-logo="{logo}" group-title="Futbol Libre",{f"Deporte {i:02d}"}\n'
            m3u_content += f'#EXTVLCOPT:http-user-agent="{USER_AGENT}"\n'
            m3u_content += f'{link_stream}\n'
            
        print("Escribiendo archivos M3U y XML")
        print(f"Eventos descartados por falta de stream: {eventos_descartados_sin_stream}")
        print(f"Streams finales escritos en M3U: {streams_finales}")
        XML_FILE = M3U_FILE.replace(".m3u", ".xml")
        # Guardamos para el XML
        generar_xmltv(datos_para_xml, XML_FILE)

        with open(M3U_FILE, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        
        print("Actualizando Threadfin")

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

        stream_pool.close()
        stream_pool = None
            
        print(f"\nGrilla de {MAX_CHANNELS} canales actualizada en Threadfin.")

    finally:
        if stream_pool is not None:
            try:
                stream_pool.close()
            except Exception as error:
                print(f"[Stream] Error cerrando workers: {error}")
        try:
            driver.quit()
        except WebDriverException:
            pass

if __name__ == "__main__":
    extraer_todo_futbol_libre()
