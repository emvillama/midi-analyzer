# midi-analyzer

A desktop app that takes a YouTube URL of a piano performance, transcribes it to MIDI, and analyzes it for technical practice patterns — scales, arpeggios, large jumps, repeated notes, chord density, and hand independence. Output is a short, prioritized list of what to practice, plus a score breakdown per pattern.

Analysis is performance-specific: the same piece played by two different pianists can produce different recommendations, since detection runs on the actual notes and timing of that recording — not a lookup of the piece itself.

## How it works

```
YouTube URL → download audio → transcribe to MIDI → detect patterns → recommend practice areas
```

Each stage is a separate step, both in the backend (four distinct endpoints) and in the UI (a pipeline view showing progress through download → transcribe → analyze → recommend). This is deliberate — it gives the user visibility into what's actually happening on longer/slower runs, rather than a single opaque "processing..." spinner.

1. **Download** — `yt-dlp` pulls audio from the given YouTube URL and extracts it to `.wav` via `ffmpeg`.
2. **Transcribe** — [basic-pitch](https://github.com/spotify/basic-pitch) (Spotify's audio-to-MIDI model) converts the `.wav` into a list of notes (pitch, start, end, velocity).
3. **Analyze** — six rule-based pattern detectors score the notes 0–100 on scale runs, arpeggios, large jumps, repeated notes, chord density, and hand independence, plus timestamps of where each pattern occurs.
4. **Recommend** — patterns above a threshold score are turned into a sorted, human-readable practice list.

The analysis layer is fully rule-based today — no LLM or external API is involved — but the pipeline is intentionally modular so a narrative/LLM layer could be added on top of the raw scores later without restructuring anything.

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Python 3.10, FastAPI |
| Desktop shell | pywebview |
| Audio download | yt-dlp + ffmpeg |
| Transcription | basic-pitch (Spotify), pretty_midi |
| Packaging | PyInstaller (Windows `.exe`) |
| Frontend | vanilla HTML/CSS/JS, dark mode, DM Mono + Syne |

## Project structure

```
midi-analyzer/
├── backend/
│   ├── main.py            FastAPI app, endpoints, pywebview launch
│   ├── downloader.py      YouTube → wav (yt-dlp + ffmpeg)
│   ├── transcriber.py     wav → MIDI notes (basic-pitch)
│   ├── analyzer.py        MIDI notes → pattern scores + timestamps
│   └── recommender.py     pattern scores → practice recommendations
├── frontend/
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── css/style.css
│       ├── js/app.js
│       └── fonts/         vendored DM Mono + Syne (.woff2)
├── bin/                   bundled ffmpeg.exe / ffprobe.exe (Windows build)
├── tests/                 pytest test suite
├── temp/                  downloaded audio (gitignored except structure)
└── .github/workflows/
    └── build.yml           PyInstaller CI build (windows-latest)
```

## Setup

### Prerequisites

- **Python 3.10** — required. Python 3.12 is incompatible with basic-pitch/TensorFlow; use [deadsnakes PPA](https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa) on Ubuntu if 3.10 isn't your system default.
- **ffmpeg** — bundled in `bin/` for the packaged Windows build; on Linux/dev, install via your package manager.
- **Node.js** — only needed if you're touching the yt-dlp `js_runtimes` extractor path.

### Linux / WSL (development)

pywebview on Ubuntu needs GTK/WebKit system packages:

```bash
sudo apt install gir1.2-webkit2-4.1 libcairo2-dev libgirepository1.0-dev
```

> Note: `gir1.2-webkit2-4.1`, **not** `4.0` — the older package name will fail silently on newer Ubuntu releases.

### Install

```bash
python3.10 -m venv venv
source venv/bin/activate        # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Known dependency landmines

| Issue | Fix |
|---|---|
| `resampy` 0.4.2 is broken | Upgrade to `resampy>=0.4.3` |
| NumPy 2.x breaks `tflite_runtime` | Pin `numpy<2` |
| Python 3.12 breaks basic-pitch/TensorFlow | Use Python 3.10 |
| `tflite-runtime` has no Windows wheels | Swap for `tensorflow` on Windows builds (already handled in `build.yml`) |

### Run

```bash
python -m backend.main
```

This starts the FastAPI server on a background thread and opens the pywebview desktop window pointed at it.

## API

All endpoints are local-only (`127.0.0.1`), called in sequence by the frontend pipeline.

| Endpoint | Method | Body | Returns |
|---|---|---|---|
| `/health` | GET | — | `{"status": "ok"}` — used by the frontend to confirm the backend is ready before starting a run |
| `/download` | POST | `{"url": "..."}` | `{"wav_path": "..."}` |
| `/transcribe` | POST | `{"wav_path": "..."}` | `{"notes": [...]}` |
| `/analyze` | POST | `{"notes": [...]}` | `{"scores": {...}}` |
| `/recommend` | POST | `{"scores": {...}}` | `{"recommendations": [...]}` |

Error responses use standard FastAPI `HTTPException` with a `detail` message:

- `400` — invalid input (e.g. malformed/non-YouTube URL, unavailable video)
- `404` — referenced file not found (e.g. bad `wav_path`)
- `422` — transcription failed on otherwise-valid input (corrupt/unsupported audio)
- `500` — unexpected server error

CORS is restricted to the app's own origin (`http://127.0.0.1:8000` / `http://localhost:8000`) rather than wildcarded, since the frontend and backend are always served from the same local process.

## Frontend notes

- `MOCK = true` in `app.js` runs the UI against fixture data without a live backend — useful for pure frontend iteration.
- Fonts (DM Mono, Syne) are vendored locally under `frontend/static/fonts/` — no runtime dependency on Google Fonts, so the app works fully offline.
- `waitForBackend()` polls `/health` before the first real pipeline run, to avoid a race between the pywebview window rendering and the uvicorn server finishing startup.

## Testing

```bash
pytest tests/
```

Test files exist per backend module (`test_downloader.py`, `test_transcriber.py`, `test_analyzer.py`, `test_recommender.py`).

## Packaging (Windows `.exe`)

Built via GitHub Actions (`.github/workflows/build.yml`) on `windows-latest`, triggered manually via `workflow_dispatch`. Key points if you're touching the build:

- `sys._MEIPASS` is used to resolve bundled paths at runtime (see `_get_ffmpeg_dir()` in `downloader.py` and `BASE_DIR` in `main.py`).
- `ffmpeg.exe` / `ffprobe.exe` live in `bin/` at the repo root and are bundled via `--add-data "bin;."`.
- Windows builds use `tensorflow` instead of `tflite-runtime` (no Windows wheels available for the latter).

## Known limitations / open items

- Downloaded `.wav` files in `temp/` are not yet cleaned up after a run completes.
- Frontend does not yet render pattern timestamps as clickable YouTube deep-links (`https://youtu.be/{video_id}?t={seconds}`) — the data is present in the API response but unused in the UI.
- No dedicated API-level test suite yet (existing tests exercise backend modules directly, not the FastAPI endpoints).

## Roadmap ideas

- Lightweight history/library view (past analyses, tags, search) vs. a heavier practice-management system (queues, status, notes per analysis) — not yet decided.
- Optional LLM layer for narrative-style output on top of the existing rule-based scores (architecture already supports slotting this in without restructuring `analyzer.py`/`recommender.py`).