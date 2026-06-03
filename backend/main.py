import threading
import uvicorn
import webview
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os

from backend.downloader import download_audio
from backend.transcriber import transcribe
from backend.analyzer import analyze
from backend.recommender import recommend


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PORT = 8000

# Resolve paths relative to this file so they work after PyInstaller bundling
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_DIR    = os.path.join(BASE_DIR, "frontend", "static")

# Serve frontend/static/ at /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── root ───────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(os.path.join(TEMPLATES_DIR, "index.html"))


# ── request models ─────────────────────────────────────────────────────────────

class DownloadRequest(BaseModel):
    url: str

class TranscribeRequest(BaseModel):
    wav_path: str

class AnalyzeRequest(BaseModel):
    notes: list[dict]

class RecommendRequest(BaseModel):
    scores: dict[str, float]


# ── endpoints ──────────────────────────────────────────────────────────────────

@app.post("/download")
def download(req: DownloadRequest):
    try:
        wav_path = download_audio(req.url)
        return {"wav_path": wav_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe")
def transcribe_audio(req: TranscribeRequest):
    try:
        notes = transcribe(req.wav_path)
        return {"notes": notes}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze")
def analyze_notes(req: AnalyzeRequest):
    try:
        scores = analyze(req.notes)
        return {"scores": scores}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend")
def get_recommendations(req: RecommendRequest):
    try:
        recs = recommend(req.scores)
        return {"recommendations": recs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── app launch ─────────────────────────────────────────────────────────────────

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def main():
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    webview.create_window(
        title="MIDI Analyzer",
        url=f"http://127.0.0.1:{PORT}",
        width=800,
        height=600,
        resizable=True,
    )
    webview.start()


if __name__ == "__main__":
    main()