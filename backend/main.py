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

from backend.downloader import download_audio, list_downloads, DOWNLOAD_DIR, _YOUTUBE_ID_RE
from backend.transcriber import transcribe, warm_up
from backend.analyzer import analyze
from backend.recommender import recommend
from backend.loops import list_loops, add_loop, delete_loop
from backend import analysis_cache


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

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEMPLATES_DIR = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_DIR    = os.path.join(BASE_DIR, "frontend", "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Set once the basic-pitch model has finished loading in the background.
# Exposed via /health so the frontend can show a "warming up" state
# instead of letting the first real /transcribe call eat the load cost.
_model_ready = threading.Event()


# ── root ───────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(os.path.join(TEMPLATES_DIR, "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "model_ready": _model_ready.is_set()}


# ── request models ─────────────────────────────────────────────────────────────

class DownloadRequest(BaseModel):
    url: str

class TranscribeRequest(BaseModel):
    wav_path: str

class AnalyzeRequest(BaseModel):
    notes: list[dict]
    video_id: str | None = None  # optional: enables score caching

class RecommendRequest(BaseModel):
    scores: dict[str, dict]
    video_id: str | None = None  # optional: enables recommendation caching

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


@app.get("/analysis/{video_id}")
def get_cached_analysis(video_id: str):
    """
    Full cached pipeline result for a video, for instant redisplay when
    reopening something from history instead of re-running
    transcribe/analyze/recommend from scratch. Any stage not yet cached
    (or invalidated because the wav changed) comes back null — the
    frontend falls back to (re-)running that stage normally.
    """
    cached = analysis_cache.get_cached(video_id)
    if cached is None:
        return {"notes": None, "scores": None, "recommendations": None}
    return cached


@app.get("/audio/{video_id}")
def get_audio(video_id: str):
    """
    Streams the cached wav for a video so the frontend can play it in-app
    (e.g. for the piano-roll tutorial view), instead of only being able to
    open YouTube externally.

    video_id is validated against YouTube's 11-char ID shape (same
    validator downloader.py uses) and the resolved path is re-checked to
    still live inside DOWNLOAD_DIR before being served, since video_id
    ultimately comes from the URL path.
    """
    if not _YOUTUBE_ID_RE.match(video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID.")

    wav_path = os.path.abspath(os.path.join(DOWNLOAD_DIR, f"{video_id}.wav"))
    download_dir_abs = os.path.abspath(DOWNLOAD_DIR)
    if not wav_path.startswith(download_dir_abs + os.sep):
        raise HTTPException(status_code=400, detail="Invalid video ID.")

    if not os.path.isfile(wav_path) or os.path.getsize(wav_path) == 0:
        raise HTTPException(status_code=404, detail="Audio not found for this video.")

    return FileResponse(
        wav_path,
        media_type="audio/wav",
        headers={"Content-Disposition": f'inline; filename="{video_id}.wav"'},
    )


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
    video_id = os.path.splitext(os.path.basename(req.wav_path))[0]

    cached = analysis_cache.get_cached(video_id)
    if cached and cached.get("notes") is not None:
        return {"notes": cached["notes"], "cached": True}

    try:
        notes = transcribe(req.wav_path)
        analysis_cache.save_notes(video_id, notes)
        return {"notes": notes, "cached": False}
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
        if req.video_id:
            analysis_cache.save_scores(req.video_id, scores)
        return {"scores": scores}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend")
def get_recommendations(req: RecommendRequest):
    try:
        recs = recommend(req.scores)
        if req.video_id:
            analysis_cache.save_recommendations(req.video_id, recs)
        return {"recommendations": recs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── app launch ─────────────────────────────────────────────────────────────────

_ALLOWED_EXTERNAL_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
}


class Api:
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


def _warm_up_model():
    try:
        warm_up()
    finally:
        _model_ready.set()


def main():
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Load the basic-pitch model in the background while the window opens,
    # instead of paying that cost on the first /transcribe call.
    threading.Thread(target=_warm_up_model, daemon=True).start()

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