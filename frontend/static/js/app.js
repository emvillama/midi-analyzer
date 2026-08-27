const API = 'http://127.0.0.1:8000';

// ── mock mode ─────────────────────────────────────────────────────────────────
// Set to true to test the UI without the backend running.
// Open index.html directly in a browser and it will use fake data.
 
const MOCK = false;
 
const MOCK_DATA = {
  download:  { wav_path: 'temp/cVYH-7QGE-A.wav' },
  transcribe: { notes: Array(2252).fill({ pitch: 60, start: 0, end: 0.5, velocity: 80 }) },
  analyze:   { scores: {
    scale_runs:        { score: 8.3,   timestamps: [12.4] },
    arpeggios:          { score: 77.9,  timestamps: [4.2, 18.7, 41.0] },
    large_jumps:        { score: 100,   timestamps: [2.1, 9.9, 30.5, 55.2] },
    repeated_notes:     { score: 10.4,  timestamps: [] },
    chord_density:       { score: 92.5,  timestamps: [6.0, 22.3, 47.8] },
    hand_independence:   { score: 100,   timestamps: [1.2, 8.4, 33.6] },
  } },
  recommend: { recommendations: [
    { label: 'Hand independence',              timestamps: [1.2, 8.4, 33.6] },
    { label: 'Large jumps / position shifts',   timestamps: [2.1, 9.9, 30.5, 55.2] },
    { label: 'Chord playing',                   timestamps: [6.0, 22.3, 47.8] },
    { label: 'Arpeggios',                       timestamps: [4.2, 18.7, 41.0] },
  ] },
  history: { history: [
    {
      video_id: 'cVYH-7QGE-A',
      title: 'Clair de Lune - Debussy (Valentina Lisitsa)',
      url: 'https://www.youtube.com/watch?v=cVYH-7QGE-A',
      wav_path: 'temp/cVYH-7QGE-A.wav',
      downloaded_at: '2026-08-20T14:02:11+00:00',
      last_used_at: '2026-08-25T09:41:00+00:00',
    },
    {
      video_id: 'fake0000002',
      title: 'Fantaisie-Impromptu - Chopin (Yuja Wang)',
      url: 'https://www.youtube.com/watch?v=fake0000002',
      wav_path: 'temp/fake0000002.wav',
      downloaded_at: '2026-08-18T10:00:00+00:00',
      last_used_at: '2026-08-18T10:00:00+00:00',
    },
  ] },
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
const historySection = document.getElementById('history-section');
const historyList    = document.getElementById('history-list');
const playerWrap     = document.getElementById('player-wrap');

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
  stopLoop();
  playerWrap.classList.remove('active');
  if (ytPlayer && typeof ytPlayer.stopVideo === 'function') {
    ytPlayer.stopVideo();
  }
  Object.keys(steps).forEach(s => setStep(s, null, 'waiting...'));
  urlInput.value = '';
  analyzeBtn.disabled = false;
  urlInput.focus();
}

// ── api calls ─────────────────────────────────────────────────────────────────

// Generous per-endpoint timeouts (ms). Download/transcribe can legitimately
// take a while on long videos or slower machines; analyze/recommend are pure
// local computation and should always be fast.
const TIMEOUTS = {
  download:   120000,
  transcribe: 180000,
  analyze:     30000,
  recommend:   15000,
};

async function post(endpoint, body) {
  const timeoutMs = TIMEOUTS[endpoint] ?? 30000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API}/${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error(
        `The ${endpoint} step took too long (over ${Math.round(timeoutMs / 1000)}s) and was cancelled. ` +
        'This can happen with very long videos or a slow connection — try a shorter clip or try again.'
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

// ── practice player (embedded YouTube video, click-a-timestamp-to-loop) ────

let ytApiReady   = false;
let ytApiLoading = false;
let ytPlayer     = null;
let pendingVideoId = null;
let loopTimer   = null;
let loopRange   = null;
let activeChip  = null;

const LOOP_LEAD_IN   = 1;   // seconds before the flagged timestamp to start
const LOOP_DURATION  = 6;   // seconds the loop plays before repeating

function loadYouTubeApi() {
  if (ytApiReady || ytApiLoading) return;
  ytApiLoading = true;

  window.onYouTubeIframeAPIReady = () => {
    ytApiReady = true;
    if (pendingVideoId) {
      createYtPlayer(pendingVideoId);
      pendingVideoId = null;
    }
  };

  const tag = document.createElement('script');
  tag.src = 'https://www.youtube.com/iframe_api';
  const firstScript = document.getElementsByTagName('script')[0];
  firstScript.parentNode.insertBefore(tag, firstScript);
}

function createYtPlayer(videoId) {
  ytPlayer = new YT.Player('yt-player', {
    videoId,
    playerVars: { rel: 0 },
  });
}

function loadPlayerVideo(videoId) {
  stopLoop();
  if (!videoId) return;

  if (!ytApiReady) {
    pendingVideoId = videoId;
    loadYouTubeApi();
    return;
  }

  if (ytPlayer && typeof ytPlayer.cueVideoById === 'function') {
    ytPlayer.cueVideoById(videoId);
  } else {
    createYtPlayer(videoId);
  }
}

function videoIdFromWavPath(wavPath) {
  const base = (wavPath || '').split(/[\\/]/).pop() || '';
  return base.replace(/\.wav$/i, '');
}

function formatTimestamp(seconds) {
  const total = Math.max(0, Math.round(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function stopLoop() {
  if (loopTimer) {
    clearInterval(loopTimer);
    loopTimer = null;
  }
  loopRange = null;
  if (activeChip) {
    activeChip.classList.remove('active');
    activeChip = null;
  }
}

function seekAndLoop(startSeconds, chipEl) {
  if (!ytPlayer || typeof ytPlayer.seekTo !== 'function') return;

  // Clicking the currently-looping chip again toggles it off.
  if (activeChip === chipEl) {
    stopLoop();
    if (typeof ytPlayer.pauseVideo === 'function') ytPlayer.pauseVideo();
    return;
  }

  stopLoop();
  if (chipEl) {
    chipEl.classList.add('active');
    activeChip = chipEl;
  }

  const start = Math.max(0, startSeconds - LOOP_LEAD_IN);
  const end = start + LOOP_DURATION;
  loopRange = { start, end };

  ytPlayer.seekTo(start, true);
  ytPlayer.playVideo();

  loopTimer = setInterval(() => {
    if (!ytPlayer || !loopRange || typeof ytPlayer.getCurrentTime !== 'function') return;
    if (ytPlayer.getCurrentTime() >= loopRange.end) {
      ytPlayer.seekTo(loopRange.start, true);
    }
  }, 300);
}

// ── render results ────────────────────────────────────────────────────────────

function renderResults(recommendations, scores, videoId) {
  recList.innerHTML = '';
  scoresGrid.innerHTML = '';

  // Practice player
  if (videoId) {
    playerWrap.classList.add('active');
    loadPlayerVideo(videoId);
  } else {
    playerWrap.classList.remove('active');
  }

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

      const row = document.createElement('div');
      row.className = 'rec-item-row';
      row.innerHTML = `<span class="rec-bullet"></span><span class="rec-text">${rec.label}</span>`;
      li.appendChild(row);

      if (videoId && rec.timestamps && rec.timestamps.length > 0) {
        const chips = document.createElement('div');
        chips.className = 'rec-timestamps';
        rec.timestamps.forEach(ts => {
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'timestamp-chip';
          chip.textContent = formatTimestamp(ts);
          chip.addEventListener('click', () => seekAndLoop(ts, chip));
          chips.appendChild(chip);
        });
        li.appendChild(chips);
      }

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
        <div class="score-bar-fill" style="width: ${val.score}%"></div>
      </div>
      <div class="score-value">${Math.round(val.score)}</div>
    `;
    scoresGrid.appendChild(card);
  });

  resultsSection.style.display = 'flex';
}

async function waitForBackend(retries = 5, delayMs = 400) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(`${API}/health`);
      if (res.ok) return true;
    } catch (_) {
      // backend not up yet, keep retrying
    }
    await new Promise(r => setTimeout(r, delayMs));
  }
  return false;
}

// ── history (previously analyzed pieces) ────────────────────────────────────

function formatRelativeTime(isoString) {
  const then = new Date(isoString).getTime();
  if (Number.isNaN(then)) return '';
  const diffMs = Date.now() - then;
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(isoString).toLocaleDateString();
}

function renderHistory(items) {
  historyList.innerHTML = '';

  if (!items || items.length === 0) {
    historySection.style.display = 'none';
    return;
  }

  items.forEach(item => {
    const li = document.createElement('li');
    li.className = 'history-item';
    li.innerHTML = `
      <span class="history-title">${item.title || item.video_id}</span>
      <span class="history-meta">${formatRelativeTime(item.last_used_at)}</span>
    `;
    li.addEventListener('click', () => runPipeline({
      url: item.url,
      wavPath: item.wav_path,
      title: item.title || item.video_id,
    }));
    historyList.appendChild(li);
  });

  historySection.style.display = 'block';
}

async function loadHistory() {
  try {
    if (MOCK) {
      renderHistory(MOCK_DATA.history.history);
      return;
    }
    const res = await fetch(`${API}/history`);
    if (!res.ok) return; // non-fatal — just don't show history
    const { history } = await res.json();
    renderHistory(history);
  } catch (_) {
    // backend not reachable yet, or /history failed — fail silently,
    // history is a convenience feature, not core to the pipeline
  }
}

// ── main pipeline ─────────────────────────────────────────────────────────────

async function runPipeline({ url, wavPath, title } = {}) {
  analyzeBtn.disabled = true;
  pipelineSection.style.display = 'block';
  errorSection.style.display    = 'none';
  resultsSection.style.display  = 'none';

  try {
    if (!MOCK) {
      setStep('download', 'active', 'connecting...');
      const ready = await waitForBackend();
      if (!ready) {
        throw new Error('Backend is still starting up. Please try again in a moment.');
      }
    }

    // 1. Download (skipped entirely when revisiting a piece we already have a wav for)
    let resolvedWavPath = wavPath;
    if (resolvedWavPath) {
      setStep('download', 'done', title ? `reusing: ${title}` : resolvedWavPath);
    } else {
      setStep('download', 'active', 'downloading audio...');
      const result = await post('download', { url });
      resolvedWavPath = result.wav_path;
      setStep('download', 'done', resolvedWavPath);
    }

    // 2. Transcribe
    setStep('transcribe', 'active', 'transcribing to midi...');
    const { notes } = await post('transcribe', { wav_path: resolvedWavPath });
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
    const videoId = videoIdFromWavPath(resolvedWavPath);
    renderResults(recommendations, scores, videoId);

    // Refresh history — a fresh download adds a new entry, a revisit bumps last_used_at
    loadHistory();

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
  runPipeline({ url });
});

urlInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') analyzeBtn.click();
});

resetBtn.addEventListener('click', reset);

// ── init ──────────────────────────────────────────────────────────────────────

loadHistory();