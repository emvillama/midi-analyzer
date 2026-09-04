import json
import os
import uuid
from datetime import datetime, timezone

from .appdata import get_app_data_dir

LOOPS_PATH = os.path.join(get_app_data_dir(), "loops.json")

MAX_NAME_LENGTH = 80


def _load_loops() -> dict:
    if not os.path.exists(LOOPS_PATH):
        return {}
    try:
        with open(LOOPS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable file shouldn't break the app — treat as
        # empty going forward rather than crashing every request.
        return {}


def _save_loops(data: dict) -> None:
    # Write to a temp file then atomically replace, so a crash mid-write
    # can't leave loops.json half-written/corrupt.
    tmp_path = LOOPS_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, LOOPS_PATH)


def list_loops(video_id: str) -> list[dict]:
    """Custom loops saved for this video, in chronological (start-time) order."""
    data = _load_loops()
    loops = data.get(video_id, [])
    return sorted(loops, key=lambda loop: loop["start"])


def add_loop(video_id: str, name: str, start: float, end: float) -> dict:
    """
    Create and persist a new custom loop for a video.

    Raises ValueError on invalid input (empty/too-long name, missing or
    out-of-order start/end).
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Loop name cannot be empty.")
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Loop name must be {MAX_NAME_LENGTH} characters or fewer.")
    if start is None or end is None:
        raise ValueError("Loop must have a start and end time.")
    if start < 0:
        raise ValueError("Loop start cannot be negative.")
    if end <= start:
        raise ValueError("Loop end must be after its start.")

    loop = {
        "id":         uuid.uuid4().hex[:8],
        "name":       name,
        "start":      round(float(start), 2),
        "end":        round(float(end), 2),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    data = _load_loops()
    data.setdefault(video_id, []).append(loop)
    _save_loops(data)

    return loop


def delete_loop(video_id: str, loop_id: str) -> bool:
    """Remove a loop by id. Returns True if it was found and removed."""
    data = _load_loops()
    loops = data.get(video_id, [])
    remaining = [loop for loop in loops if loop["id"] != loop_id]
    if len(remaining) == len(loops):
        return False
    data[video_id] = remaining
    _save_loops(data)
    return True