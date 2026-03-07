import os
from dotenv import load_dotenv
import http.server
import socketserver
import threading
import requests
import socket
import time

load_dotenv()

# --- CONFIGURACIÓN ---
THREADFIN_API_URL = os.getenv("THREADFIN_API_URL")
LOCAL_PORT = os.getenv("LOCAL_PORT")
M3U_FILE = os.getenv("M3U_FILE")

def obtener_mi_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

def iniciar_servidor():
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", int(LOCAL_PORT)), handler) as httpd:
        print(f"[HTTP] Sirviendo por 30s M3U en: http://{obtener_mi_ip()}:{LOCAL_PORT}/{M3U_FILE}")
        httpd.timeout = 30
        httpd.handle_request()
        time.sleep(5)
        print("Archivo entregado o tiempo cumplido. Cerrando servidor.")

def cargar_en_threadfin():
    mythread = threading.Thread(target=iniciar_servidor, daemon=True)
    print("[Info] Servidor activo.")
    #time.sleep(2)
    
    print(f"[Threadfin] Intentando forzar actualización...")
    
    # Intentamos con dos comandos distintos para saltar el bloqueo 423
    comandos = [
        {"cmd": "update.m3u"}, # Actualizar fuentes
        {"cmd": "save.m3u"}    # Forzar guardado y re-escaneo
    ]
    
    for payload in comandos:
        try:
            response = requests.post(f"{THREADFIN_API_URL}", json=payload)
            if response.status_code == 200:
                print(f"[Threadfin] OK: Comando {payload['cmd']} aceptado.")
            elif response.status_code == 423:
                print(f"[Threadfin] El servidor está bloqueado (423). Esperando 5 segundos...")
                time.sleep(5)
            else:
                print(f"[Threadfin] Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"[Threadfin] Error de conexión: {e}")
    mythread.start()
if __name__ == "__main__":
    cargar_en_threadfin()
    print("[Info] Proceso finalizado.")    