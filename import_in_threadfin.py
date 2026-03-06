import http.server
import socketserver
import threading
import requests
import socket
import time

# --- CONFIGURACIÓN ---
THREADFIN_URL = "http://192.168.0.149:34400"
PUERTO_LOCAL = 8080
ARCHIVO_M3U = "agenda_futbol.m3u"

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
    with socketserver.TCPServer(("", PUERTO_LOCAL), handler) as httpd:
        print(f"[HTTP] Sirviendo M3U en: http://{obtener_mi_ip()}:{PUERTO_LOCAL}/{ARCHIVO_M3U}")
        httpd.serve_forever()

def cargar_en_threadfin():
    threading.Thread(target=iniciar_servidor, daemon=True).start()
    time.sleep(2)
    
    print(f"[Threadfin] Intentando forzar actualización...")
    
    # Intentamos con dos comandos distintos para saltar el bloqueo 423
    comandos = [
        {"cmd": "update.m3u"}, # Actualizar fuentes
        {"cmd": "save.m3u"}    # Forzar guardado y re-escaneo
    ]
    
    for payload in comandos:
        try:
            response = requests.post(f"{THREADFIN_URL}/api/", json=payload)
            if response.status_code == 200:
                print(f"[Threadfin] OK: Comando {payload['cmd']} aceptado.")
            elif response.status_code == 423:
                print(f"[Threadfin] El servidor está bloqueado (423). Esperando 5 segundos...")
                time.sleep(5)
            else:
                print(f"[Threadfin] Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"[Threadfin] Error de conexión: {e}")

    print("[Info] Servidor activo. Presiona Ctrl+C para cerrar una vez que Threadfin cargue.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nServidor cerrado.")

if __name__ == "__main__":
    cargar_en_threadfin()