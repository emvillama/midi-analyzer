import threading
import uvicorn
import webview
import webbrowser
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import sys

from backend.downloader import download_audio, list_downloads
from backend.transcriber import transcribe
from backend.analyzer import analyze
from backend.recommender import recommend
from backend.loops import list_loops, add_loop, delete_loop


app = FastAPI()

PORT = 8000

ALLOWED_ORIGINS = [
    f"http://127.0.0.1:{PORT}",
    f"http://localhost:{PORT}",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Resolve paths relative to this file so they work after PyInstaller bundling
# otherwise fall back to the project root relative to this file.
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEMPLATES_DIR = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_DIR    = os.path.join(BASE_DIR, "frontend", "static")

# Serve frontend/static/ at /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── root ───────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(os.path.join(TEMPLATES_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok"}


# ── request models ─────────────────────────────────────────────────────────────

class DownloadRequest(BaseModel):
    url: str

class TranscribeRequest(BaseModel):
    wav_path: str

class AnalyzeRequest(BaseModel):
    notes: list[dict]

class RecommendRequest(BaseModel):
    scores: dict[str, dict]

class CreateLoopRequest(BaseModel):
    video_id: str
    name: str
    start: float
    end: float


# ── endpoints ──────────────────────────────────────────────────────────────────

@app.get("/history")
def history():
    try:
        return {"history": list_downloads()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/loops/{video_id}")
def get_loops(video_id: str):
    try:
        return {"loops": list_loops(video_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/loops")
def create_loop(req: CreateLoopRequest):
    try:
        loop = add_loop(req.video_id, req.name, req.start, req.end)
        return {"loop": loop}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/loops/{video_id}/{loop_id}")
def remove_loop(video_id: str, loop_id: str):
    try:
        deleted = delete_loop(video_id, loop_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Loop not found.")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/download")
def download(req: DownloadRequest):
    try:
        wav_path = download_audio(req.url)
        return {"wav_path": wav_path}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe")
def transcribe_audio(req: TranscribeRequest):
    try:
        notes = transcribe(req.wav_path)
        return {"notes": notes}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
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

_ALLOWED_EXTERNAL_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
}


class Api:
    """
    Exposed to the frontend as `pywebview.api.*`. The embedded WebKitGTK
    view often can't play YouTube's embedded player (missing codec/DRM
    support), even when the YouTube iframe itself loads without raising a
    JS API error — so the reliable fix is opening the video in the user's
    actual system browser instead, which has real codec support.
    """

    def open_external(self, url: str) -> bool:
        try:
            host = (urlparse(url).hostname or "").lower()
        except ValueError:
            return False
        if host not in _ALLOWED_EXTERNAL_HOSTS:
            return False
        return webbrowser.open(url)


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
        js_api=Api(),
    )
    webview.start()


if __name__ == "__main__":
    main()