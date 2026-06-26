import yt_dlp
import os
import sys

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "temp")


def _get_ffmpeg_dir() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # PyInstaller extracts bin/ contents here
    return os.path.join(os.path.dirname(__file__), "..", "bin")


def download_audio(url: str) -> str:
    """
    Takes a YouTube URL, downloads the audio as a wav file.
    Returns the file path of the downloaded audio.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
        "ffmpeg_location": _get_ffmpeg_dir(),
        "quiet": True,
        "extractor_args": {"youtube": {"js_runtimes": ["nodejs"]}},
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info["id"]
        audio_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.wav")

    return audio_path