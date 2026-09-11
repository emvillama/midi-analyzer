const API = 'http://127.0.0.1:8000';

// ── mock mode ─────────────────────────────────────────────────────────────────
// Set to true to test the UI without the backend running.
// Open index.html directly in a browser and it will use fake data.
 
const MOCK = false;
 
const MOCK_DATA = {
  download:  { wav_path: 'temp/cVYH-7QGE-A.wav' },
  transcribe: { notes: Array(2252).fill({ pitch: 60, start: 0, end: 0.5, velocity: 80 }) },
  analyze:   { scores: {
    scale_runs:        { score: 8.3,   sections: [{ start: 11.9, end: 15.4 }] },
    arpeggios:          { score: 77.9,  sections: [{ start: 3.5, end: 7.8 }, { start: 17.9, end: 22.1 }, { start: 40.2, end: 44.6 }] },
    large_jumps:        { score: 100,   sections: [{ start: 1.6, end: 5.2 }, { start: 9.1, end: 13.9 }, { start: 29.8, end: 34.0 }, { start: 54.5, end: 58.3 }] },
    repeated_notes:     { score: 10.4,  sections: [] },
    chord_density:       { score: 92.5,  sections: [{ start: 5.4, end: 9.1 }, { start: 21.7, end: 26.5 }, { start: 47.1, end: 51.0 }] },
    hand_independence:   { score: 100,   sections: [{ start: 0.6, end: 5.0 }, { start: 7.8, end: 11.6 }, { start: 32.9, end: 37.2 }] },
  } },
  recommend: { recommendations: [
    { label: 'Hand independence',              sections: [{ start: 0.6, end: 5.0 }, { start: 7.8, end: 11.6 }, { start: 32.9, end: 37.2 }] },
    { label: 'Large jumps / position shifts',   sections: [{ start: 1.6, end: 5.2 }, { start: 9.1, end: 13.9 }, { start: 29.8, end: 34.0 }, { start: 54.5, end: 58.3 }] },
    { label: 'Chord playing',                   sections: [{ start: 5.4, end: 9.1 }, { start: 21.7, end: 26.5 }, { start: 47.1, end: 51.0 }] },
    { label: 'Arpeggios',                       sections: [{ start: 3.5, end: 7.8 }, { start: 17.9, end: 22.1 }, { start: 40.2, end: 44.6 }] },
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
  loops: {
    'cVYH-7QGE-A': [
      { id: 'mockloop1', name: 'Left hand jump section', start: 12.0, end: 18.5, created_at: '2026-08-24T10:00:00+00:00' },
    ],
  },
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
const playerError     = document.getElementById('player-error');
const playerOpenBtn   = document.getElementById('player-open-btn');
const loopsSection = document.getElementById('loops-section');
const loopCreator  = document.getElementById('loop-creator');
const loopList     = document.getElementById('loop-list');
const tutorialSection    = document.getElementById('tutorial-section');
const tutorialPlayer     = document.getElementById('tutorial-player');
const tutorialVisualizer = document.getElementById('tutorial-visualizer');

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
  hidePlayerError();
  playerWrap.classList.remove('active');
  loopsSection.classList.remove('active');
  currentLoops = [];
  loopList.innerHTML = '';
  resetLoopCreator();
  teardownTutorial();
  currentVideoId = null;
  lastSeekSeconds = null;
  updatePlayerOpenBtnLabel();
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
//
// The embedded WebKitGTK view often can't actually play YouTube's embedded
// player (missing codec/DRM support) — and YouTube frequently fails
// *silently* from the JS API's point of view (no onError fires; YouTube's
// own "can't play this video" message just renders inside the iframe). So
// rather than depending on error detection, a persistent "watch on
// YouTube" button always launches the video in the user's real system
// browser — which has proper codec support — synced to whichever
// timestamp was last tapped.

let ytApiReady   = false;
let ytApiLoading = false;
let ytPlayer     = null;
let pendingVideoId  = null;
let currentVideoId  = null;
let lastSeekSeconds = null;
let loopTimer   = null;
let loopRange   = null;
let activeChip  = null;

// (loop timing now comes from the actual detected section's start/end,
// computed server-side in analyzer.py — no fixed window needed here)

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
    events: {
      onError: () => showPlayerError(),
      onReady: () => {
        if (loopCreationState === 'idle') renderLoopCreator();
      },
    },
  });
}

function showPlayerError() {
  playerError.style.display = 'flex';
}

function hidePlayerError() {
  playerError.style.display = 'none';
}

function loadPlayerVideo(videoId) {
  stopLoop();
  hidePlayerError();
  if (!videoId) return;
  currentVideoId = videoId;
  lastSeekSeconds = null;
  updatePlayerOpenBtnLabel();

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

// Opens a URL in the user's actual system browser via pywebview's JS API
// bridge (Api.open_external in main.py) — falls back to window.open for
// contexts without the pywebview bridge (e.g. testing in a plain browser).
async function openExternal(url) {
  try {
    if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.open_external === 'function') {
      const opened = await window.pywebview.api.open_external(url);
      if (opened) return;
    }
  } catch (_) {
    // fall through to window.open
  }
  window.open(url, '_blank');
}

function buildWatchUrl() {
  if (!currentVideoId) return null;
  const base = `https://www.youtube.com/watch?v=${currentVideoId}`;
  return lastSeekSeconds != null ? `${base}&t=${Math.floor(lastSeekSeconds)}s` : base;
}

function updatePlayerOpenBtnLabel() {
  playerOpenBtn.textContent = lastSeekSeconds != null
    ? `watch on youtube · ${formatTimestamp(lastSeekSeconds)} ↗`
    : 'watch on youtube ↗';
}

playerOpenBtn.addEventListener('click', () => {
  const url = buildWatchUrl();
  if (url) openExternal(url);
});

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

function formatRange(start, end) {
  return `${formatTimestamp(start)}–${formatTimestamp(end)}`;
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

function seekAndLoop(section, chipEl) {
  // Keep the "watch on youtube" button synced to whichever section was
  // last tapped, regardless of whether the embedded player can actually
  // play it — this is the reliable path, not a fallback.
  lastSeekSeconds = section.start;
  updatePlayerOpenBtnLabel();

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

  // Use the actual detected passage boundaries (already padded with a
  // lead-in/lead-out by the analyzer) rather than a synthetic fixed window
  // — the loop now matches the real musical section, not an arbitrary
  // few-second guess.
  loopRange = { start: section.start, end: section.end };

  ytPlayer.seekTo(section.start, true);
  ytPlayer.playVideo();

  loopTimer = setInterval(() => {
    if (!ytPlayer || !loopRange || typeof ytPlayer.getCurrentTime !== 'function') return;
    if (ytPlayer.getCurrentTime() >= loopRange.end) {
      ytPlayer.seekTo(loopRange.start, true);
    }
  }, 300);
}

// ── visual tutorial (falling notes, via html-midi-player) ──────────────────
//
// <midi-player> loads the transcribed .mid file (served by the backend's
// /midi/{video_id} endpoint) and drives <midi-visualizer type="waterfall">
// automatically — no custom animation-loop or sync code needed. Playback
// is a synthesized rendition via the player's built-in soundfont, not the
// original recording; that's what keeps sound and falling notes perfectly
// in sync for free. (The embedded YouTube player above, and "watch on
// youtube", still give access to the real recording.)

function setupTutorial(videoId, notes) {
  if (!videoId || !notes || notes.length === 0) {
    teardownTutorial();
    return;
  }

  tutorialSection.classList.add('active');

  // In MOCK mode there's no backend to stream a .mid file from.
  if (!MOCK) {
    tutorialPlayer.stop();
    tutorialPlayer.src = `${API}/midi/${videoId}`;
  }
}

function teardownTutorial() {
  tutorialSection.classList.remove('active');
  if (tutorialPlayer.stop) tutorialPlayer.stop();
  tutorialPlayer.removeAttribute('src');
}

// ── custom loops (user-created, named, saved across sessions) ──────────────

let currentLoops = [];               // loops for the currently loaded video
let loopCreationState = 'idle';      // 'idle' | 'marking-start' | 'marking-end' | 'naming'
let pendingLoopStart = null;
let pendingLoopEnd = null;

function playerCanCaptureTime() {
  return !!(ytPlayer && typeof ytPlayer.getCurrentTime === 'function');
}

function renderLoopCreator() {
  loopCreator.innerHTML = '';

  if (loopCreationState === 'idle') {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'loop-create-btn';
    btn.textContent = '+ create loop';
    const disabled = !playerCanCaptureTime();
    btn.disabled = disabled;
    if (disabled) {
      btn.title = "Video playback isn't available, so loop points can't be captured.";
    }
    btn.addEventListener('click', () => {
      loopCreationState = 'marking-start';
      renderLoopCreator();
    });
    loopCreator.appendChild(btn);
    return;
  }

  if (loopCreationState === 'marking-start' || loopCreationState === 'marking-end') {
    const msg = document.createElement('p');
    msg.className = 'loop-creator-msg';
    msg.textContent = loopCreationState === 'marking-start'
      ? 'Play the video, then click below at the moment the loop should start.'
      : `Start set at ${formatTimestamp(pendingLoopStart)}. Now click below at the moment it should end.`;
    loopCreator.appendChild(msg);

    const row = document.createElement('div');
    row.className = 'loop-creator-row';

    const markBtn = document.createElement('button');
    markBtn.type = 'button';
    markBtn.className = 'loop-creator-btn';
    markBtn.textContent = loopCreationState === 'marking-start' ? 'start loop here' : 'end loop here';
    markBtn.addEventListener('click', handleMarkClick);
    row.appendChild(markBtn);

    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'loop-creator-cancel-btn';
    cancelBtn.textContent = 'cancel';
    cancelBtn.addEventListener('click', resetLoopCreator);
    row.appendChild(cancelBtn);

    loopCreator.appendChild(row);
    return;
  }

  if (loopCreationState === 'naming') {
    const msg = document.createElement('p');
    msg.className = 'loop-creator-msg';
    msg.textContent = `Loop: ${formatRange(pendingLoopStart, pendingLoopEnd)}. Name it to save:`;
    loopCreator.appendChild(msg);

    const row = document.createElement('div');
    row.className = 'loop-creator-row';

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'loop-name-input';
    input.placeholder = 'e.g. left hand jump section';
    input.maxLength = 80;
    row.appendChild(input);

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'loop-creator-btn';
    saveBtn.textContent = 'save';
    saveBtn.addEventListener('click', () => saveLoopFromCreator(input.value));
    row.appendChild(saveBtn);

    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'loop-creator-cancel-btn';
    cancelBtn.textContent = 'cancel';
    cancelBtn.addEventListener('click', resetLoopCreator);
    row.appendChild(cancelBtn);

    loopCreator.appendChild(row);
    input.focus();
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') saveBtn.click();
    });
    return;
  }
}

function handleMarkClick() {
  if (!playerCanCaptureTime()) {
    resetLoopCreator();
    return;
  }
  const t = ytPlayer.getCurrentTime();

  if (loopCreationState === 'marking-start') {
    pendingLoopStart = t;
    loopCreationState = 'marking-end';
    renderLoopCreator();
    return;
  }

  if (loopCreationState === 'marking-end') {
    if (t <= pendingLoopStart) {
      showLoopCreatorError('The end point must be after the start point — try again.');
      return;
    }
    pendingLoopEnd = t;
    loopCreationState = 'naming';
    renderLoopCreator();
  }
}

function showLoopCreatorError(message) {
  let err = loopCreator.querySelector('.loop-creator-error');
  if (!err) {
    err = document.createElement('p');
    err.className = 'loop-creator-error';
    loopCreator.appendChild(err);
  }
  err.textContent = message;
}

function resetLoopCreator() {
  loopCreationState = 'idle';
  pendingLoopStart = null;
  pendingLoopEnd = null;
  renderLoopCreator();
}

async function saveLoopFromCreator(rawName) {
  const name = rawName.trim();
  if (!name) {
    showLoopCreatorError('Give the loop a name before saving.');
    return;
  }
  if (!currentVideoId) return;

  try {
    let loop;
    if (MOCK) {
      loop = { id: `mockloop-${Date.now()}`, name, start: pendingLoopStart, end: pendingLoopEnd, created_at: new Date().toISOString() };
    } else {
      const res = await fetch(`${API}/loops`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_id: currentVideoId, name, start: pendingLoopStart, end: pendingLoopEnd }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        showLoopCreatorError(err.detail || 'Could not save loop.');
        return;
      }
      ({ loop } = await res.json());
    }
    currentLoops.push(loop);
    currentLoops.sort((a, b) => a.start - b.start);
    resetLoopCreator();
    renderLoopList();
  } catch (err) {
    showLoopCreatorError('Could not save loop: ' + err.message);
  }
}

function renderLoopList() {
  loopList.innerHTML = '';

  currentLoops.forEach(loop => {
    const li = document.createElement('li');
    li.className = 'loop-item';

    const playBtn = document.createElement('button');
    playBtn.type = 'button';
    playBtn.className = 'loop-item-play';

    const nameSpan = document.createElement('span');
    nameSpan.className = 'loop-item-name';
    nameSpan.textContent = loop.name;

    const rangeSpan = document.createElement('span');
    rangeSpan.className = 'loop-item-range';
    rangeSpan.textContent = formatRange(loop.start, loop.end);

    playBtn.appendChild(nameSpan);
    playBtn.appendChild(rangeSpan);
    playBtn.addEventListener('click', () => seekAndLoop({ start: loop.start, end: loop.end }, playBtn));
    li.appendChild(playBtn);

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'loop-item-delete';
    deleteBtn.setAttribute('aria-label', `Delete loop "${loop.name}"`);
    deleteBtn.textContent = '×';
    deleteBtn.addEventListener('click', () => deleteLoopItem(loop, li, playBtn));
    li.appendChild(deleteBtn);

    loopList.appendChild(li);
  });
}

async function deleteLoopItem(loop, liEl, playBtnEl) {
  if (!currentVideoId) return;
  if (!MOCK) {
    try {
      const res = await fetch(`${API}/loops/${currentVideoId}/${loop.id}`, { method: 'DELETE' });
      if (!res.ok && res.status !== 404) {
        console.warn('Failed to delete loop', loop.id, res.status);
        return;
      }
    } catch (err) {
      console.warn('Failed to delete loop', err.message);
      return;
    }
  }
  if (activeChip === playBtnEl) stopLoop();
  currentLoops = currentLoops.filter(l => l.id !== loop.id);
  liEl.remove();
}

async function loadLoopsForVideo(videoId) {
  currentLoops = [];
  resetLoopCreator();
  if (!videoId) {
    renderLoopList();
    return;
  }
  try {
    if (MOCK) {
      currentLoops = (MOCK_DATA.loops && MOCK_DATA.loops[videoId]) || [];
    } else {
      const res = await fetch(`${API}/loops/${videoId}`);
      if (res.ok) {
        const data = await res.json();
        currentLoops = data.loops || [];
      }
    }
  } catch (err) {
    // Loops are a convenience feature — fail silently rather than
    // interrupting the rest of the results from rendering.
  }
  renderLoopList();
}

// ── render results ────────────────────────────────────────────────────────────

function renderResults(recommendations, scores, videoId, notes) {
  recList.innerHTML = '';
  scoresGrid.innerHTML = '';

  // Practice player
  if (videoId) {
    playerWrap.classList.add('active');
    loadPlayerVideo(videoId);
  } else {
    playerWrap.classList.remove('active');
  }

  // Visual tutorial (falling notes, synced to in-app audio playback)
  setupTutorial(videoId, notes);

  // Custom loops
  if (videoId) {
    loopsSection.classList.add('active');
    loadLoopsForVideo(videoId);
  } else {
    loopsSection.classList.remove('active');
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

      if (videoId && rec.sections && rec.sections.length > 0) {
        const chips = document.createElement('div');
        chips.className = 'rec-timestamps';
        rec.sections.forEach(section => {
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'timestamp-chip';
          chip.textContent = formatRange(section.start, section.end);
          chip.addEventListener('click', () => seekAndLoop(section, chip));
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

async function waitForBackend(retries = 20, delayMs = 700) {
  for (let i = 0; i < retries; i++) {
    try {
      const res = await fetch(`${API}/health`);
      if (res.ok) return true;
      console.warn(`[waitForBackend] attempt ${i + 1}/${retries}: got HTTP ${res.status}`);
    } catch (err) {
      // Most likely cause on Windows: a firewall prompt is blocking the
      // connection until the user clicks "Allow access", or the freshly
      // launched .exe is still being scanned by antivirus. Logged (not
      // swallowed) so it's visible in devtools if this keeps happening.
      console.warn(`[waitForBackend] attempt ${i + 1}/${retries} failed:`, err.message);
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
      setStep('download', 'active', 'connecting to backend...');
      const ready = await waitForBackend();
      if (!ready) {
        throw new Error(
          'Could not reach the backend after several attempts. If a Windows ' +
          'Firewall prompt appeared for this app, click "Allow access" and try ' +
          'again — otherwise, try restarting the app.'
        );
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
    renderResults(recommendations, scores, videoId, notes);

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