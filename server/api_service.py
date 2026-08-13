import xml.etree.ElementTree as ET
import re
import os
import threading
import subprocess
from flask import Flask, jsonify, request, render_template_string
from dotenv import set_key, load_dotenv

app = Flask(__name__)
XML_PATH = "/opt/threadfin/eventos.xml"
ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))

task_state = {
    "is_running": False,
    "error": False,
    "message": "",
    "output": []
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configuración de Fútbol Libre</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --glass-bg: rgba(30, 41, 59, 0.7);
            --glass-border: rgba(255, 255, 255, 0.1);
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }
        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(16, 185, 129, 0.1) 0px, transparent 50%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            width: 100%;
            max-width: 600px;
            padding: 2rem;
            background: var(--glass-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--glass-border);
            border-radius: 1rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            margin: 2rem;
        }
        h1 {
            margin-top: 0;
            font-size: 1.5rem;
            font-weight: 600;
            text-align: center;
            margin-bottom: 0.5rem;
        }
        p.subtitle {
            color: var(--text-muted);
            text-align: center;
            font-size: 0.875rem;
            margin-bottom: 2rem;
        }
        .form-group {
            margin-bottom: 1.5rem;
        }
        label {
            display: block;
            font-size: 0.875rem;
            font-weight: 500;
            margin-bottom: 0.5rem;
            color: var(--text-muted);
        }
        input[type="text"] {
            width: 100%;
            padding: 0.75rem 1rem;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--glass-border);
            border-radius: 0.5rem;
            color: var(--text-main);
            font-size: 1rem;
            box-sizing: border-box;
            outline: none;
            transition: all 0.2s;
        }
        input[type="text"]:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
        }
        button {
            width: 100%;
            padding: 0.875rem;
            background-color: var(--primary);
            color: white;
            border: none;
            border-radius: 0.5rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s, transform 0.1s;
        }
        button:hover {
            background-color: var(--primary-hover);
        }
        button:active {
            transform: scale(0.98);
        }
        button:disabled {
            background-color: #475569;
            cursor: not-allowed;
            transform: none;
        }
        .status-container {
            margin-top: 1.5rem;
            padding: 1rem;
            border-radius: 0.5rem;
            display: none;
            font-size: 0.875rem;
            text-align: center;
        }
        .status-running {
            display: block;
            background: rgba(59, 130, 246, 0.1);
            border: 1px solid rgba(59, 130, 246, 0.2);
            color: #60a5fa;
        }
        .status-success {
            display: block;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            color: #34d399;
        }
        .status-error {
            display: block;
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: #f87171;
            word-wrap: break-word;
        }
        .spinner {
            display: inline-block;
            width: 1rem;
            height: 1rem;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: #fff;
            animation: spin 1s ease-in-out infinite;
            vertical-align: text-bottom;
            margin-right: 0.5rem;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .terminal {
            margin-top: 1.5rem;
            background: #000;
            border-radius: 0.5rem;
            padding: 1rem;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.85rem;
            color: #a3e635;
            height: 250px;
            overflow-y: auto;
            display: none;
            text-align: left;
            border: 1px solid var(--glass-border);
            line-height: 1.4;
        }
        .terminal.visible {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Configuración de Fútbol Libre</h1>
        <p class="subtitle">Actualiza la URL base para extraer los eventos</p>
        
        <div class="form-group">
            <label for="url">FUTBOL_LIBRE_URL</label>
            <input type="text" id="url" value="{{ current_url }}" placeholder="https://ejemplo.com/">
        </div>
        
        <button id="updateBtn" onclick="updateUrl()">Actualizar y Sincronizar</button>
        
        <div id="statusBox" class="status-container">
            <span id="spinner" class="spinner" style="display:none;"></span>
            <span id="statusText">Iniciando actualización...</span>
        </div>
        
        <div id="terminal" class="terminal"></div>
    </div>

    <script>
        let pollInterval;
        let lastOutputLength = 0;

        function updateUrl() {
            const url = document.getElementById('url').value;
            const btn = document.getElementById('updateBtn');
            const statusBox = document.getElementById('statusBox');
            const statusText = document.getElementById('statusText');
            const spinner = document.getElementById('spinner');
            const terminal = document.getElementById('terminal');

            if (!url) return;

            btn.disabled = true;
            statusBox.className = 'status-container status-running';
            spinner.style.display = 'inline-block';
            statusText.innerText = 'Actualizando .env e iniciando script...';
            
            terminal.innerHTML = '';
            terminal.classList.add('visible');
            lastOutputLength = 0;

            fetch('/update-url', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    statusText.innerText = 'Script ejecutándose. Revisa la consola abajo...';
                    pollInterval = setInterval(checkStatus, 1000);
                } else {
                    showError(data.error || 'Error desconocido al iniciar.');
                }
            })
            .catch(err => {
                showError('Error de red al intentar actualizar.');
            });
        }

        function checkStatus() {
            fetch('/status')
            .then(res => res.json())
            .then(data => {
                updateTerminal(data.output);
                
                if (!data.is_running) {
                    clearInterval(pollInterval);
                    if (data.error) {
                        showError('Script finalizado con errores.');
                    } else {
                        showSuccess('¡Actualización completada exitosamente!');
                    }
                }
            })
            .catch(err => {
                clearInterval(pollInterval);
                showError('Error de red al consultar el estado.');
            });
        }
        
        function updateTerminal(outputLines) {
            const terminal = document.getElementById('terminal');
            if (!outputLines || outputLines.length === 0) return;
            
            if (outputLines.length > lastOutputLength) {
                const newLines = outputLines.slice(lastOutputLength);
                for (const line of newLines) {
                    const div = document.createElement('div');
                    div.textContent = line;
                    terminal.appendChild(div);
                }
                lastOutputLength = outputLines.length;
                terminal.scrollTop = terminal.scrollHeight;
            }
        }

        function showError(msg) {
            const btn = document.getElementById('updateBtn');
            const statusBox = document.getElementById('statusBox');
            const statusText = document.getElementById('statusText');
            const spinner = document.getElementById('spinner');
            
            btn.disabled = false;
            spinner.style.display = 'none';
            statusBox.className = 'status-container status-error';
            statusText.innerText = msg;
        }

        function showSuccess(msg) {
            const btn = document.getElementById('updateBtn');
            const statusBox = document.getElementById('statusBox');
            const statusText = document.getElementById('statusText');
            const spinner = document.getElementById('spinner');
            
            btn.disabled = false;
            spinner.style.display = 'none';
            statusBox.className = 'status-container status-success';
            statusText.innerText = msg;
        }
    </script>
</body>
</html>
"""

def run_update_script():
    global task_state
    try:
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'update-futbollibre.sh'))
        
        process = subprocess.Popen(
            ['bash', script_path], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            cwd=os.path.dirname(script_path),
            bufsize=1
        )
        
        for line in iter(process.stdout.readline, ''):
            if line:
                task_state["output"].append(line.rstrip('\\n'))
        
        process.stdout.close()
        return_code = process.wait()
        
        task_state["is_running"] = False
        if return_code == 0:
            task_state["error"] = False
            task_state["message"] = "Terminado."
            task_state["output"].append("--- Proceso finalizado con éxito ---")
        else:
            task_state["error"] = True
            task_state["message"] = f"Falló con código {return_code}"
            task_state["output"].append(f"--- El script reportó un fallo (Código {return_code}) ---")
            
    except Exception as e:
        task_state["is_running"] = False
        task_state["error"] = True
        task_state["message"] = str(e)
        task_state["output"].append(f"Error interno: {str(e)}")

@app.route('/', methods=['GET'])
def index():
    load_dotenv(ENV_PATH)
    current_url = os.getenv("FUTBOL_LIBRE_URL", "")
    return render_template_string(HTML_TEMPLATE, current_url=current_url)

@app.route('/update-url', methods=['POST'])
def update_url():
    global task_state
    
    if task_state["is_running"]:
        return jsonify({"success": False, "error": "Ya hay una actualización en curso."}), 400
        
    data = request.get_json()
    new_url = data.get('url')
    
    if not new_url:
        return jsonify({"success": False, "error": "URL no proporcionada."}), 400
        
    try:
        set_key(ENV_PATH, "FUTBOL_LIBRE_URL", new_url)
        
        task_state["is_running"] = True
        task_state["error"] = False
        task_state["message"] = "Iniciando..."
        task_state["output"] = []
        
        thread = threading.Thread(target=run_update_script)
        thread.daemon = True
        thread.start()
        
        return jsonify({"success": True})
    except Exception as e:
        task_state["is_running"] = False
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "is_running": task_state["is_running"],
        "error": task_state["error"],
        "message": task_state["message"],
        "output": task_state["output"]
    })

@app.route('/grilla', methods=['GET'])
def get_grilla():
    if not os.path.exists(XML_PATH):
        return jsonify([])
    try:
        tree = ET.parse(XML_PATH)
        root = tree.getroot()
        partidos = []

        canales = {child.get('id'): child.find('display-name').text 
                   for child in root.findall('channel')}

        for prog in root.findall('programme'):
            titulo_raw = prog.find('title').text if prog.find('title') is not None else ""
            if "Slot Libre" in titulo_raw:
                continue
            
            match = re.search(r'\[(\d{2}:\d{2})\]\s*(.*)', titulo_raw)
            if match:
                hora_real = match.group(1)
                evento_limpio = match.group(2)
                evento_limpio = evento_limpio.replace("PROXIMAMENTE: ", "").strip()
                canal_id = prog.get('channel')
                nombre_canal = canales.get(canal_id, canal_id)

                partidos.append({
                    "hora": hora_real,
                    "evento": evento_limpio,
                    "canal": nombre_canal
                })

        partidos.sort(key=lambda x: x['hora'])
        return jsonify(partidos)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)