let poller;

function setStatus(element, message, kind) {
  element.textContent = message;
  element.className = `status ${kind || ''}`;
}

function pollStatus(button, status, tail) {
  fetch('/status').then(response => response.json()).then(data => {
    tail.textContent = data.output.join('\n');
    tail.scrollTop = tail.scrollHeight;
    if (data.is_running) {
      setStatus(status, data.message || 'Ejecutando...', '');
      return;
    }
    clearInterval(poller);
    button.disabled = false;
    setStatus(status, data.error ? data.message : 'Proceso terminado correctamente.', data.error ? 'error' : 'success');
  }).catch(() => {
    clearInterval(poller);
    button.disabled = false;
    setStatus(status, 'No se pudo consultar el estado.', 'error');
  });
}

function updateUrl() {
  const button = document.getElementById('run');
  const status = document.getElementById('status');
  const tail = document.getElementById('tail');
  const url = document.getElementById('url').value.trim();
  if (!url) return setStatus(status, 'La URL es obligatoria.', 'error');
  button.disabled = true;
  tail.textContent = '';
  fetch('/update-url', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({url}) })
    .then(response => response.json().then(data => ({ok: response.ok, data})))
    .then(result => {
      if (!result.ok && result.data.running) {
        tail.textContent = (result.data.status.output || []).join('\n');
        poller = setInterval(() => pollStatus(button, status, tail), 1000);
        throw new Error('Ya hay un proceso corriendo; mostrando su log.');
      }
      if (!result.ok) throw new Error(result.data.error || 'No se pudo iniciar.');
      poller = setInterval(() => pollStatus(button, status, tail), 1000);
    }).catch(error => {
      if (!error.message.startsWith('Ya hay un proceso')) {
        button.disabled = false;
        setStatus(status, error.message, 'error');
      }
    });
}

function stopUpdate() {
  const runButton = document.getElementById('run');
  const stopButton = document.getElementById('stop');
  const status = document.getElementById('status');
  stopButton.disabled = true;
  fetch('/stop-update', {method: 'POST'})
    .then(response => response.json().then(data => ({ok: response.ok, data})))
    .then(result => {
      stopButton.disabled = false;
      if (!result.ok) return setStatus(status, result.data.error, 'error');
      runButton.disabled = false;
      setStatus(status, result.data.message, 'success');
      if (poller) clearInterval(poller);
    }).catch(() => { stopButton.disabled = false; setStatus(status, 'No se pudo detener el proceso.', 'error'); });
}

window.addEventListener('DOMContentLoaded', () => {
  const runButton = document.getElementById('run');
  const status = document.getElementById('status');
  const tail = document.getElementById('tail');
  fetch('/status').then(response => response.json()).then(data => {
    if (data.is_running) {
      runButton.disabled = true;
      tail.textContent = data.output.join('\n');
      poller = setInterval(() => pollStatus(runButton, status, tail), 1000);
    }
  });
});

function updateSystem(target, button) {
  const status = document.getElementById('system-status');
  button.disabled = true;
  fetch(`/system-update/${target}`, {method: 'POST'})
    .then(response => response.json().then(data => ({ok: response.ok, data})))
    .then(result => {
      button.disabled = false;
      setStatus(status, result.data.message || result.data.error, result.ok ? 'success' : 'error');
    }).catch(() => { button.disabled = false; setStatus(status, 'No se pudo actualizar el sistema.', 'error'); });
}
