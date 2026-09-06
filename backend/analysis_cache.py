import os
import json
from typing import Optional

from backend.downloader import DOWNLOAD_DIR

CACHE_PATH = os.path.join(DOWNLOAD_DIR, "analysis_cache.json")


def _load() -> dict:
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(cache: dict) -> None:
    tmp_path = CACHE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
    os.replace(tmp_path, CACHE_PATH)


def _wav_mtime(video_id: str) -> Optional[float]:
    wav_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.wav")
    try:
        return os.path.getmtime(wav_path)
    except OSError:
        return None


def _fresh_entry(cache: dict, video_id: str, mtime: float) -> dict:
    """
    The cached entry for this video_id, or a blank one if there wasn't one
    yet or the wav on disk has changed since it was cached. mtime is the
    freshness signal — same filesystem-as-source-of-truth approach used
    for download history, so a re-download naturally invalidates stale
    notes/scores instead of silently serving them.
    """
    entry = cache.get(video_id)
    if not entry or entry.get("wav_mtime") != mtime:
        return {"wav_mtime": mtime}
    return entry


def get_cached(video_id: str) -> Optional[dict]:
    """
    {"notes": ..., "scores": ..., "recommendations": ...} for this
    video_id if the wav is unchanged since caching, else None. Any of the
    three fields may be None if the pipeline hasn't reached that stage
    yet for this video.
    """
    mtime = _wav_mtime(video_id)
    if mtime is None:
        return None
    entry = _load().get(video_id)
    if not entry or entry.get("wav_mtime") != mtime:
        return None
    return {k: entry.get(k) for k in ("notes", "scores", "recommendations")}


def save_notes(video_id: str, notes: list[dict]) -> None:
    _update(video_id, "notes", notes)


def save_scores(video_id: str, scores: dict) -> None:
    _update(video_id, "scores", scores)


def save_recommendations(video_id: str, recommendations: list[dict]) -> None:
    _update(video_id, "recommendations", recommendations)


def _update(video_id: str, field: str, value) -> None:
    mtime = _wav_mtime(video_id)
    if mtime is None:
        return  # no wav on disk for this id — nothing to key the cache to
    cache = _load()
    entry = _fresh_entry(cache, video_id, mtime)
    entry[field] = value
    cache[video_id] = entry
    _save(cache)