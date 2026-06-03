import threading
import uvicorn
import webview
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


# request models ─────────────────────────────────────────────────────────────

class DownloadRequest(BaseModel):
    url: str

class TranscribeRequest(BaseModel):
    wav_path: str

class AnalyzeRequest(BaseModel):
    notes: list[dict]

class RecommendRequest(BaseModel):
    scores: dict[str, float]


# endpoints ──────────────────────────────────────────────────────────────────

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


# app launch ─────────────────────────────────────────────────────────────────

def start_server():
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def main():
    # Start FastAPI in a background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Launch pywebview window pointed at the local server
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