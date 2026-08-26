import yt_dlp
import os
import re
import sys
from urllib.parse import urlparse

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "temp")

# Matches youtube.com/watch?v=, youtu.be/, youtube.com/shorts/, m.youtube.com, etc.
_YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtu.be",
}
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _extract_video_id(url: str) -> str | None:
    """Best-effort extraction of an 11-char YouTube video ID from a URL, or None."""
    parsed = urlparse(url)
    if parsed.hostname is None or parsed.hostname.lower() not in _YOUTUBE_HOSTS:
        return None

    if parsed.hostname.lower() == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
    else:
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts and path_parts[0] in ("shorts", "embed", "live") and len(path_parts) > 1:
            candidate = path_parts[1]
        else:
            from urllib.parse import parse_qs
            candidate = parse_qs(parsed.query).get("v", [None])[0]

    if candidate and _YOUTUBE_ID_RE.match(candidate):
        return candidate
    return None


def is_valid_youtube_url(url: str) -> bool:
    """True if `url` looks like a well-formed YouTube video/shorts/short-link URL."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return False
    return _extract_video_id(url) is not None


def _get_ffmpeg_dir() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # PyInstaller extracts bin/ contents here
    return os.path.join(os.path.dirname(__file__), "..", "bin")


def download_audio(url: str) -> str:
    """
    Takes a YouTube URL, downloads the audio as a wav file.
    Returns the file path of the downloaded audio.

    If this video was already downloaded (a non-empty wav for its video ID
    already exists in the temp dir), the existing file is reused instead of
    re-downloading and re-extracting audio from scratch.
    """
    if not is_valid_youtube_url(url):
        raise ValueError(
            f"'{url}' doesn't look like a valid YouTube video URL. "
            "Expected something like https://youtube.com/watch?v=... or https://youtu.be/..."
        )

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    video_id = _extract_video_id(url)
    if video_id:
        existing_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.wav")
        if os.path.exists(existing_path) and os.path.getsize(existing_path) > 0:
            return existing_path

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
        if not info or "id" not in info:
            raise ValueError(
                f"Could not extract audio from '{url}'. "
                "It may be a playlist, private, age-restricted, or otherwise unavailable video."
            )
        video_id = info["id"]
        audio_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.wav")

    return audio_path