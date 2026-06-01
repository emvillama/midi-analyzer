# midi-analyzer — Project Context

## What This Project Is
A piano practice assistant that:
1. Takes a YouTube URL from the user
2. Downloads the audio from the video
3. Transcribes the audio to MIDI (detects notes and timing)
4. Analyzes the MIDI for technical patterns (scales, arpeggios, jumps, etc.)
5. Outputs a simple list of recommended practice techniques

## Example Output
```
Recommended practice:
- Scales
- Arpeggios
- Octave jumps
```

## Key Decisions Made
- **No AI layer** — fully rule-based pattern detection. Claude API can be added later in ~a few hours of work by passing pattern scores JSON to Claude and replacing the bullet list output with a narrative response.
- **Input is YouTube URL** — not a MIDI file upload. Audio is downloaded and transcribed locally.
- **End goal is a .exe** — bundled with PyInstaller + pywebview for Windows distribution.
- **Analysis is performance-specific** — the same piece by different artists may get different recommendations based on what's actually played.

## Tech Stack
| Layer | Tool |
|---|---|
| Language | Python 3.10 |
| UI framework | pywebview (HTML/CSS/JS rendered in a native window) |
| Audio download | yt-dlp |
| Audio to MIDI | basic-pitch (Spotify, tflite-runtime backend) |
| MIDI parsing | pretty_midi + mido |
| Backend server | FastAPI + uvicorn |
| Bundling to .exe | PyInstaller |
| Version control | Git + GitHub |
| Editor | VS Code (WSL terminal) |
| OS | Ubuntu (WSL) |

## Environment
- Python version: 3.10.20 (via deadsnakes PPA)
- Virtual environment: `~/midi-analyzer/venv` (Python 3.10)
- Activate venv: `source venv/bin/activate`
- GitHub repo: https://github.com/emvillama/midi-analyzer
- Branch: master

## Project Folder Structure
```
midi-analyzer/
├── backend/
│   ├── __init__.py
│   ├── main.py          # Entry point — pywebview app launcher
│   ├── downloader.py    # yt-dlp: YouTube URL → .wav file
│   ├── transcriber.py   # basic-pitch: .wav → MIDI note data
│   ├── analyzer.py      # Rule-based pattern detection → scores JSON
│   └── recommender.py   # Scores JSON → practice recommendation list
├── frontend/
│   ├── templates/
│   │   └── index.html   # Main UI
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── temp/                # Downloaded audio files (gitignored)
├── venv/                # Python virtual environment (gitignored)
├── .gitignore
├── requirements.txt
└── README.md
```

## Pipeline
```
YouTube URL
    → downloader.py      → temp/{video_id}.wav
    → transcriber.py     → MIDI note data (pitch, timing, velocity)
    → analyzer.py        → pattern scores JSON e.g. {"scale_runs": 72, "arpeggios": 45}
    → recommender.py     → ["Scales", "Arpeggios", "Octave jumps"]
    → frontend           → displayed to user
```

## Pattern Detection (analyzer.py — not built yet)
Rule-based logic, no ML. Each pattern gets a prominence score 0–100.

| Pattern | Detection Logic |
|---|---|
| Scale runs | Stepwise motion (semitone/whole tone intervals), 4+ consecutive notes |
| Arpeggios | Chord tones (3rds/5ths apart), ascending/descending, non-simultaneous |
| Large jumps | Interval > minor 6th between consecutive notes |
| Repeated notes | Same pitch within short time window |
| Chord density | Simultaneous notes per beat |
| Hand independence | Diverging rhythmic patterns between left/right hand channels |

Scores are tempo-normalized — a pattern at ♩=160 scores higher than the same pattern at ♩=60.

## Modules — Current Status

### ✅ downloader.py — COMPLETE
Takes a YouTube URL, downloads audio as .wav to `temp/` folder.
```python
from backend.downloader import download_audio
path = download_audio("https://www.youtube.com/watch?v=...")
# returns: "temp/{video_id}.wav"
```
Note: yt-dlp shows a JS runtime warning (nodejs installed but not auto-detected). Warning is non-critical — audio downloads correctly.

### 🔲 transcriber.py — NOT STARTED
Will use basic-pitch to convert .wav → MIDI note data.
Input: path to .wav file
Output: list of notes with pitch, start time, end time, velocity

### 🔲 analyzer.py — NOT STARTED
Will take MIDI note data and run rule-based pattern detection.
Input: list of notes
Output: JSON scores dict e.g. `{"scale_runs": 72, "arpeggios": 45, "large_jumps": 30}`

### 🔲 recommender.py — NOT STARTED
Will map scores to a practice recommendation list.
Input: scores JSON
Output: list of strings e.g. `["Scales", "Arpeggios", "Octave jumps"]`

### 🔲 main.py — NOT STARTED
Will wire everything together and launch the pywebview window.

### 🔲 frontend — NOT STARTED
Simple HTML/CSS/JS UI. User pastes YouTube URL, clicks analyze, sees recommendation list.

## Dependencies (requirements.txt)
Key packages:
- `basic-pitch==0.4.0` — audio to MIDI transcription
- `yt-dlp` — YouTube audio download
- `pretty_midi` — MIDI parsing
- `mido` — MIDI parsing
- `fastapi` + `uvicorn` — local backend server
- `pywebview` — desktop window wrapper
- `pyinstaller` — bundle to .exe
- `tflite-runtime` — ML backend for basic-pitch
- `librosa` — audio analysis
- `scikit-learn`, `scipy`, `numpy` — scientific computing

Install all: `pip install -r requirements.txt`

## .gitignore
```
venv/
__pycache__/
*.pyc
*.mid
*.wav
*.mp3
*.mp4
dist/
build/
*.spec
.env
temp/
test_*.py
```

## Next Steps (in order)
1. Write `transcriber.py`
2. Write `analyzer.py`
3. Write `recommender.py`
4. Write `main.py`
5. Build frontend (index.html, style.css, app.js)
6. Wire everything together
7. Test end-to-end with a YouTube URL
8. Bundle to .exe with PyInstaller