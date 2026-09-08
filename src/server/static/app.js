let poller;

function setStatus(element, message, kind) {
  element.textContent = message;
  element.className = `status ${kind || ''}`;
}

function updateProgress(progress) {
  if (!progress) return;
  for (const stage of ['sites', 'streams']) {
    const percent = progress[stage]?.percent || 0;
    document.getElementById(`${stage}-progress`).value = percent;
    document.getElementById(`${stage}-progress-value`).textContent = `${percent}%`;
  }
}

function toggleChannel(row) {
  const streamRow = row.nextElementSibling;
  const expanded = !streamRow.hidden;
  streamRow.hidden = expanded;
  row.setAttribute('aria-expanded', String(!expanded));
  if (!expanded) {
    const video = streamRow.querySelector('video');
    if (video) ensureInlinePlayer(video, video.dataset.stream).catch(error => console.error(error));
  }
}

function ensureInlinePlayer(video, stream) {
  if (video.dataset.loaded === 'true') return Promise.resolve();
  video.muted = true;
  return new Promise((resolve, reject) => {
    if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = stream;
      video.addEventListener('loadedmetadata', resolve, {once: true});
      video.addEventListener('error', reject, {once: true});
      return;
    }
    if (!window.Hls || !Hls.isSupported()) return reject(new Error('HLS no soportado'));
    const hls = new Hls();
    video._hls = hls;
    hls.loadSource(stream);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, resolve);
    hls.on(Hls.Events.ERROR, (_, data) => { if (data.fatal) reject(new Error('No se pudo cargar el stream')); });
  }).then(() => { video.dataset.loaded = 'true'; });
}

function openPip(event, stream, videoId) {
  event.stopPropagation();
  const video = document.getElementById(videoId);
  video.closest('.stream-row').hidden = false;
  ensureInlinePlayer(video, stream)
    .then(() => video.play())
    .then(() => video.requestPictureInPicture())
    .catch(error => console.error('No se pudo abrir Picture-in-Picture:', error));
}

function pollStatus(button, status, tail) {
  fetch('/status').then(response => response.json()).then(data => {
    tail.textContent = data.output.join('\n');
    tail.scrollTop = tail.scrollHeight;
    updateProgress(data.progress);
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
        updateProgress(result.data.status.progress);
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
      updateProgress(data.progress);
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
