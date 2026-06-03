const API = 'http://127.0.0.1:8000';

// ── mock mode ─────────────────────────────────────────────────────────────────
// Set to true to test the UI without the backend running.
// Open index.html directly in a browser and it will use fake data.
 
const MOCK = true;
 
const MOCK_DATA = {
  download:  { wav_path: 'temp/cVYH-7QGE-A.wav' },
  transcribe: { notes: Array(2252).fill({ pitch: 60, start: 0, end: 0.5, velocity: 80 }) },
  analyze:   { scores: { scale_runs: 8.3, arpeggios: 77.9, large_jumps: 100, repeated_notes: 10.4, chord_density: 92.5, hand_independence: 100 } },
  recommend: { recommendations: ['Hand independence', 'Large jumps / position shifts', 'Chord playing', 'Arpeggios'] },
};
 
// Simulates network delay so the pipeline steps are visible
const MOCK_DELAY = { download: 800, transcribe: 1200, analyze: 600, recommend: 400 };

// ── DOM refs ──────────────────────────────────────────────────────────────────

const urlInput      = document.getElementById('url-input');
const analyzeBtn    = document.getElementById('analyze-btn');
const pipelineSection = document.getElementById('pipeline-section');
const errorSection  = document.getElementById('error-section');
const errorMsg      = document.getElementById('error-msg');
const resultsSection = document.getElementById('results-section');
const recList       = document.getElementById('rec-list');
const scoresGrid    = document.getElementById('scores-grid');
const resetBtn      = document.getElementById('reset-btn');

const steps = {
  download:   document.getElementById('step-download'),
  transcribe: document.getElementById('step-transcribe'),
  analyze:    document.getElementById('step-analyze'),
  recommend:  document.getElementById('step-recommend'),
};

const details = {
  download:   document.getElementById('detail-download'),
  transcribe: document.getElementById('detail-transcribe'),
  analyze:    document.getElementById('detail-analyze'),
  recommend:  document.getElementById('detail-recommend'),
};

// ── state helpers ─────────────────────────────────────────────────────────────

function setStep(name, state, detail) {
  const el = steps[name];
  el.classList.remove('active', 'done', 'error');
  if (state) el.classList.add(state);
  if (detail) details[name].textContent = detail;
}

function showError(msg) {
  errorSection.style.display = 'block';
  errorMsg.textContent = msg;
}

function reset() {
  pipelineSection.style.display = 'none';
  errorSection.style.display    = 'none';
  resultsSection.style.display  = 'none';
  recList.innerHTML    = '';
  scoresGrid.innerHTML = '';
  Object.keys(steps).forEach(s => setStep(s, null, 'waiting...'));
  urlInput.value = '';
  analyzeBtn.disabled = false;
  urlInput.focus();
}

// ── api calls ─────────────────────────────────────────────────────────────────

async function post(endpoint, body) {
  const res = await fetch(`${API}/${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// ── render results ────────────────────────────────────────────────────────────

function renderResults(recommendations, scores) {
  // Recommendations list
  if (recommendations.length === 0) {
    const li = document.createElement('li');
    li.className = 'rec-item';
    li.innerHTML = '<span class="rec-text" style="color:var(--muted)">No strong patterns detected.</span>';
    recList.appendChild(li);
  } else {
    recommendations.forEach(rec => {
      const li = document.createElement('li');
      li.className = 'rec-item';
      li.innerHTML = `<span class="rec-bullet"></span><span class="rec-text">${rec}</span>`;
      recList.appendChild(li);
    });
  }

  // Score cards
  const labels = {
    scale_runs:        'scale runs',
    arpeggios:         'arpeggios',
    large_jumps:       'large jumps',
    repeated_notes:    'repeated notes',
    chord_density:     'chord density',
    hand_independence: 'hand independence',
  };

  Object.entries(scores).forEach(([key, val]) => {
    const card = document.createElement('div');
    card.className = 'score-card';
    card.innerHTML = `
      <div class="score-name">${labels[key] || key}</div>
      <div class="score-bar-track">
        <div class="score-bar-fill" style="width: ${val}%"></div>
      </div>
      <div class="score-value">${Math.round(val)}</div>
    `;
    scoresGrid.appendChild(card);
  });

  resultsSection.style.display = 'flex';
}

// ── main pipeline ─────────────────────────────────────────────────────────────

async function runPipeline(url) {
  analyzeBtn.disabled = true;
  pipelineSection.style.display = 'block';
  errorSection.style.display    = 'none';
  resultsSection.style.display  = 'none';

  try {
    // 1. Download
    setStep('download', 'active', 'downloading audio...');
    const { wav_path } = await post('download', { url });
    setStep('download', 'done', wav_path);

    // 2. Transcribe
    setStep('transcribe', 'active', 'transcribing to midi...');
    const { notes } = await post('transcribe', { wav_path });
    setStep('transcribe', 'done', `${notes.length} notes detected`);

    // 3. Analyze
    setStep('analyze', 'active', 'detecting patterns...');
    const { scores } = await post('analyze', { notes });
    setStep('analyze', 'done', 'patterns scored');

    // 4. Recommend
    setStep('recommend', 'active', 'building recommendations...');
    const { recommendations } = await post('recommend', { scores });
    setStep('recommend', 'done', `${recommendations.length} recommendations`);

    // Render
    renderResults(recommendations, scores);

  } catch (err) {
    const active = Object.keys(steps).find(s => steps[s].classList.contains('active'));
    if (active) setStep(active, 'error', 'failed');
    showError(err.message);
    analyzeBtn.disabled = false;
  }
}

// ── events ────────────────────────────────────────────────────────────────────

analyzeBtn.addEventListener('click', () => {
  const url = urlInput.value.trim();
  if (!url) return urlInput.focus();
  runPipeline(url);
});

urlInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') analyzeBtn.click();
});

resetBtn.addEventListener('click', reset);