from flask import Flask, request, jsonify
import subprocess
import threading
import os

app = Flask(__name__)

# Ruta al script de actualización y al log
SCRIPT_PATH = "/root/bin/futbol/update-futbollibre.sh" 
LOG_PATH = "/var/log/log_diario.txt"

# Variable para controlar si ya se está ejecutando
is_running = False

def run_update(key):
    global is_running
    try:
        with open(LOG_PATH, "w") as log_file:
            # Ejecuta el script pasando la key como argumento
            subprocess.run(["bash", SCRIPT_PATH, key], stdout=log_file, stderr=log_file)
    finally:
        is_running = False

@app.route('/update', methods=['POST'])
def update():
    global is_running
    data = request.json
    key = data.get('key', '')

    if is_running:
        return jsonify({"status": "error", "message": "Ejecución en curso"}), 429

    is_running = True
    # Ejecutar en hilo separado para no bloquear el request de HA
    thread = threading.Thread(target=run_update, args=(key,))
    thread.start()
    
    return jsonify({"status": "success", "message": "Actualización iniciada"}), 202

@app.route('/log', methods=['GET'])
def get_log():
    if not os.path.exists(LOG_PATH):
        return jsonify({"log": "No hay logs disponibles."})
    
    with open(LOG_PATH, "r") as f:
        content = f.read()
    return jsonify({"log": content, "running": is_running})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)