import yt_dlp
import os
import re
import sys
import json
from datetime import datetime, timezone
from urllib.parse import urlparse

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "temp")
MANIFEST_PATH = os.path.join(DOWNLOAD_DIR, "downloads.json")

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


def _load_manifest() -> dict:
    if not os.path.exists(MANIFEST_PATH):
        return {}
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable manifest shouldn't break downloads/history —
        # just treat it as empty going forward.
        return {}


def _save_manifest(manifest: dict) -> None:
    # Write to a temp file then atomically replace, so a crash mid-write
    # can't leave downloads.json half-written/corrupt.
    tmp_path = MANIFEST_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp_path, MANIFEST_PATH)


def _record_download(video_id: str, url: str, wav_path: str, title: str | None = None) -> None:
    """Add/update this video's entry in the local download history."""
    manifest = _load_manifest()
    now = datetime.now(timezone.utc).isoformat()

    entry = manifest.get(video_id, {})
    entry["video_id"] = video_id
    entry["url"] = url
    entry["wav_path"] = wav_path
    if title:
        entry["title"] = title
    else:
        entry.setdefault("title", video_id)
    entry.setdefault("downloaded_at", now)
    entry["last_used_at"] = now

    manifest[video_id] = entry
    _save_manifest(manifest)


def list_downloads() -> list[dict]:
    """
    Every wav file currently present in the download directory, most
    recently modified first. The filesystem is the source of truth here —
    if a wav is deleted, it disappears from this list on the next call,
    regardless of what's in the manifest. The manifest is only used to
    attach a friendlier title/source URL when one is available; a wav with
    no manifest entry (e.g. the manifest was cleared, or the file was added
    outside the app) still shows up, just without that metadata.
    """
    if not os.path.isdir(DOWNLOAD_DIR):
        return []

    manifest = _load_manifest()

    entries = []
    for filename in os.listdir(DOWNLOAD_DIR):
        if not filename.endswith(".wav"):
            continue
        wav_path = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.getsize(wav_path) == 0:
            continue

        video_id = filename[:-len(".wav")]
        meta = manifest.get(video_id, {})

        mtime = os.path.getmtime(wav_path)
        entries.append({
            "video_id": video_id,
            "title": meta.get("title", video_id),
            "url": meta.get("url"),
            "wav_path": wav_path,
            "downloaded_at": meta.get("downloaded_at"),
            "last_used_at": meta.get("last_used_at") or datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
            "_mtime": mtime,
        })

    entries.sort(key=lambda e: (e["last_used_at"], e["_mtime"]), reverse=True)
    for e in entries:
        del e["_mtime"]

    return entries


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
            _record_download(video_id, url, existing_path)
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
        _record_download(video_id, url, audio_path, title=info.get("title"))

    return audio_path