// ── Selector de formato ───────────────────────────────────────
let selectedFormat = 'short';
let lastResult = null;

document.querySelectorAll('.format-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.format-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedFormat = btn.dataset.format;
    document.getElementById('selected-format').value = selectedFormat;
  });
});

// ── Generación de contenido ───────────────────────────────────
document.getElementById('create-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const topic = document.getElementById('topic').value.trim();
  const tone = document.getElementById('tone').value;
  const context = document.getElementById('context').value.trim();

  if (!topic) { showToast('Introduce un tema', 'error'); return; }

  setLoading(true);

  try {
    const data = await apiFetch('/api/generate-content', {
      method: 'POST',
      body: JSON.stringify({ topic, format: selectedFormat, tone, context }),
    });
    lastResult = data;
    renderPreview(data);
  } catch (err) {
    showToast(err.message || 'Error generando contenido', 'error');
    setLoading(false);
  }
});

function setLoading(loading) {
  document.getElementById('preview-empty').classList.toggle('hidden', loading || lastResult != null);
  document.getElementById('preview-loading').classList.toggle('hidden', !loading);
  document.getElementById('preview-content').classList.toggle('hidden', loading || lastResult == null);
  document.getElementById('generate-btn').disabled = loading;
}

// ── Renderizado de previsualización ───────────────────────────
function renderPreview(data) {
  const labels = { short: 'Short / Reel', carousel: 'Carrusel', post: 'Post', thread: 'Thread X' };
  document.getElementById('preview-title').textContent = labels[data.format] || data.format;
  const body = document.getElementById('preview-body');
  const s = data.structured;

  if (!s) {
    body.innerHTML = `<pre class="text-gray-300 text-sm whitespace-pre-wrap">${escHtml(data.content || '')}</pre>`;
  } else if (data.format === 'short') {
    body.innerHTML = renderShort(s);
  } else if (data.format === 'carousel') {
    body.innerHTML = renderCarousel(s);
  } else if (data.format === 'post') {
    body.innerHTML = renderPost(s);
  } else if (data.format === 'thread') {
    body.innerHTML = renderThread(s);
  } else {
    body.innerHTML = `<pre class="text-gray-300 text-sm whitespace-pre-wrap">${escHtml(JSON.stringify(s, null, 2))}</pre>`;
  }

  setLoading(false);
  document.getElementById('preview-content').classList.remove('hidden');
  document.getElementById('preview-empty').classList.add('hidden');
}

function renderShort(s) {
  const beats = (s.beats || []).map(b => `
    <div class="bg-gray-800 rounded-lg p-3">
      <p class="text-white text-sm">${escHtml(b.text)}</p>
      <p class="text-gray-400 text-xs mt-1">📝 ${escHtml(b.caption)} · ⏱ ${b.duration}s</p>
    </div>`).join('');
  const tags = (s.hashtags || []).map(h => `<span class="text-purple-400 text-xs">#${escHtml(h)}</span>`).join(' ');
  return `
    <div class="space-y-3">
      <div class="bg-purple-900/30 border border-purple-700/40 rounded-lg p-3">
        <p class="text-xs font-semibold text-purple-300 mb-1">GANCHO</p>
        <p class="text-white text-sm">${escHtml(s.hook?.text || '')}</p>
      </div>
      ${beats}
      <div class="bg-gray-800 rounded-lg p-3">
        <p class="text-xs font-semibold text-gray-400 mb-1">CTA</p>
        <p class="text-white text-sm">${escHtml(s.cta || '')}</p>
      </div>
      <div class="flex flex-wrap gap-1">${tags}</div>
    </div>`;
}

function renderCarousel(s) {
  const slides = (s.slides || []).map((sl, i) => `
    <div class="bg-gray-800 rounded-lg p-3">
      <span class="text-xs text-gray-500">${i + 1}. ${sl.type}</span>
      <p class="text-white text-sm font-semibold mt-1">${escHtml(sl.headline)}</p>
      <p class="text-gray-300 text-xs mt-1">${escHtml(sl.body)}</p>
    </div>`).join('');
  const tags = (s.hashtags || []).map(h => `<span class="text-purple-400 text-xs">#${escHtml(h)}</span>`).join(' ');
  return `<div class="space-y-2">${slides}<div class="flex flex-wrap gap-1 mt-2">${tags}</div></div>`;
}

function renderPost(s) {
  const bullets = (s.bullets || []).map(b => `<li class="text-gray-300 text-sm">${escHtml(b)}</li>`).join('');
  const tags = (s.hashtags || []).map(h => `<span class="text-purple-400 text-xs">#${escHtml(h)}</span>`).join(' ');
  return `
    <div class="space-y-3">
      <p class="text-white font-semibold text-sm">${escHtml(s.hook || '')}</p>
      <p class="text-gray-300 text-sm">${escHtml(s.body || '')}</p>
      <ul class="list-disc list-inside space-y-1">${bullets}</ul>
      <p class="text-purple-300 text-sm italic">${escHtml(s.cta || '')}</p>
      <div class="flex flex-wrap gap-1">${tags}</div>
    </div>`;
}

function renderThread(s) {
  const tweets = (s.tweets || []).map((t, i) => `
    <div class="bg-gray-800 rounded-lg p-3">
      <span class="text-xs text-gray-500">${i + 1}/${s.tweets.length}</span>
      <p class="text-white text-sm mt-1">${escHtml(t)}</p>
    </div>`).join('');
  return `<div class="space-y-2">${tweets}</div>`;
}

// ── Copiar contenido ──────────────────────────────────────────
function copyContent() {
  if (!lastResult) return;
  const text = lastResult.content || JSON.stringify(lastResult.structured, null, 2);
  copyToClipboard(text);
}

// ── Modal de guardar ──────────────────────────────────────────
function saveContent() {
  if (!lastResult) return;
  document.getElementById('save-title').value = '';
  document.getElementById('save-modal').classList.remove('hidden');
}

function closeSaveModal() {
  document.getElementById('save-modal').classList.add('hidden');
}

async function confirmSave() {
  const title = document.getElementById('save-title').value.trim();
  if (!title) { showToast('Introduce un título', 'error'); return; }

  try {
    await apiFetch('/api/contents', {
      method: 'POST',
      body: JSON.stringify({
        title,
        body: lastResult.content || JSON.stringify(lastResult.structured),
        format: lastResult.format,
        topic: document.getElementById('topic').value.trim(),
        tone: document.getElementById('tone').value,
        status: 'draft',
        metadata: lastResult.structured || {},
      }),
    });
    closeSaveModal();
    showToast('Contenido guardado en biblioteca', 'success');
  } catch (err) {
    showToast(err.message || 'Error al guardar', 'error');
  }
}
