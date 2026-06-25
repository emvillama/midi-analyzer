from collections import defaultdict

# helpers ──────────────────────────────────────────────────────────

def _estimate_tempo(notes: list[dict]) -> float:
    """Estimate BPM from median inter-onset interval."""
    if len(notes) < 2:
        return 120.0
    onsets = sorted(n["start"] for n in notes)
    iois = [onsets[i+1] - onsets[i] for i in range(len(onsets)-1) if onsets[i+1] - onsets[i] > 0.03]
    if not iois:
        return 120.0
    median_ioi = sorted(iois)[len(iois) // 2]
    return 60.0 / median_ioi


def _tempo_weight(tempo: float) -> float:
    """Scale factor: faster tempo → patterns are harder → score higher."""
    return min(tempo / 120.0, 2.0)


def _group_simultaneous(notes: list[dict], tolerance: float = 0.05) -> list[list[dict]]:
    """Group notes that start within `tolerance` seconds of each other."""
    if not notes:
        return []
    groups = []
    current = [notes[0]]
    for note in notes[1:]:
        if note["start"] - current[0]["start"] <= tolerance:
            current.append(note)
        else:
            groups.append(current)
            current = [note]
    groups.append(current)
    return groups


# pattern detectors ──────────────────────────────────────────────────────────

def _score_scale_runs(notes: list[dict], tempo: float) -> tuple[float, list[float]]:
    """Stepwise melodic motion: intervals of 1–2 semitones, 4+ consecutive notes."""
    if len(notes) < 4:
        return 0.0, []

    groups = _group_simultaneous(notes)
    melody = [min(g, key=lambda n: n["pitch"]) for g in groups if len(g) == 1]

    if len(melody) < 4:
        return 0.0, []

    run_lengths = []
    timestamps = []
    run = 1
    run_start = melody[0]["start"]
    for i in range(1, len(melody)):
        interval = abs(melody[i]["pitch"] - melody[i-1]["pitch"])
        if 1 <= interval <= 2:
            run += 1
        else:
            if run >= 4:
                run_lengths.append(run)
                timestamps.append(round(run_start, 2))
            run = 1
            run_start = melody[i]["start"]
    if run >= 4:
        run_lengths.append(run)
        timestamps.append(round(run_start, 2))

    if not run_lengths:
        return 0.0, []

    total_stepwise = sum(run_lengths)
    ratio = total_stepwise / max(len(melody), 1)
    raw = min(ratio * 150, 100)
    return min(raw * _tempo_weight(tempo), 100), timestamps


def _score_arpeggios(notes: list[dict], tempo: float) -> tuple[float, list[float]]:
    """Broken chord tones: intervals of 3–7 semitones, non-simultaneous, directional."""
    groups = _group_simultaneous(notes)
    melody = [g[0] for g in groups if len(g) == 1]

    if len(melody) < 3:
        return 0.0, []

    arp_count = 0
    timestamps = []
    run = 1
    last_dir = None
    run_start = melody[0]["start"]
    for i in range(1, len(melody)):
        interval = melody[i]["pitch"] - melody[i-1]["pitch"]
        abs_int = abs(interval)
        direction = 1 if interval > 0 else -1
        if 3 <= abs_int <= 7:
            if last_dir is None or direction == last_dir:
                run += 1
                last_dir = direction
            else:
                if run >= 3:
                    arp_count += run
                    timestamps.append(round(run_start, 2))
                run = 1
                last_dir = direction
                run_start = melody[i]["start"]
        else:
            if run >= 3:
                arp_count += run
                timestamps.append(round(run_start, 2))
            run = 1
            last_dir = None
            run_start = melody[i]["start"] if i < len(melody) else run_start
    if run >= 3:
        arp_count += run
        timestamps.append(round(run_start, 2))

    ratio = arp_count / max(len(melody), 1)
    raw = min(ratio * 200, 100)
    return min(raw * _tempo_weight(tempo), 100), timestamps


def _score_large_jumps(notes: list[dict], tempo: float) -> tuple[float, list[float]]:
    """Intervals larger than a minor 6th (8 semitones) between consecutive melody notes."""
    groups = _group_simultaneous(notes)
    melody = [g[0] for g in groups]

    if len(melody) < 2:
        return 0.0, []

    timestamps = []
    jump_count = 0
    for i in range(1, len(melody)):
        if abs(melody[i]["pitch"] - melody[i-1]["pitch"]) > 8:
            jump_count += 1
            timestamps.append(round(melody[i]["start"], 2))

    ratio = jump_count / max(len(melody), 1)
    raw = min(ratio * 300, 100)
    return min(raw * _tempo_weight(tempo), 100), timestamps


def _score_repeated_notes(notes: list[dict], tempo: float) -> tuple[float, list[float]]:
    """Same pitch repeated within a short time window (< 0.5s)."""
    if len(notes) < 2:
        return 0.0, []

    sorted_notes = sorted(notes, key=lambda n: n["start"])
    timestamps = []
    repeat_count = 0
    for i in range(1, len(sorted_notes)):
        if (sorted_notes[i]["pitch"] == sorted_notes[i-1]["pitch"]
                and (sorted_notes[i]["start"] - sorted_notes[i-1]["start"]) < 0.5):
            repeat_count += 1
            timestamps.append(round(sorted_notes[i]["start"], 2))

    ratio = repeat_count / max(len(sorted_notes), 1)
    raw = min(ratio * 300, 100)
    return min(raw * _tempo_weight(tempo), 100), timestamps


def _score_chord_density(notes: list[dict], tempo: float) -> tuple[float, list[float]]:
    """Average number of simultaneous notes per group."""
    groups = _group_simultaneous(notes)
    if not groups:
        return 0.0, []

    chord_groups = [g for g in groups if len(g) >= 3]
    timestamps = [round(g[0]["start"], 2) for g in chord_groups]
    ratio = len(chord_groups) / max(len(groups), 1)
    raw = min(ratio * 200, 100)
    return min(raw * _tempo_weight(tempo), 100), timestamps


def _score_hand_independence(notes: list[dict], tempo: float) -> tuple[float, list[float]]:
    """
    Proxy: simultaneous notes spanning a wide pitch range (> 12 semitones),
    suggesting left and right hand are doing different things.
    """
    groups = _group_simultaneous(notes)
    wide_groups = [
        g for g in groups
        if len(g) >= 2 and (max(n["pitch"] for n in g) - min(n["pitch"] for n in g)) > 12
    ]

    timestamps = [round(g[0]["start"], 2) for g in wide_groups]
    ratio = len(wide_groups) / max(len(groups), 1)
    raw = min(ratio * 200, 100)
    return min(raw * _tempo_weight(tempo), 100), timestamps


# API ──────────────────────────────────────────────────────────

def analyze(notes: list[dict]) -> dict[str, dict]:
    """
    Run all pattern detectors on a list of MIDI notes.

    Args:
        notes: Output from transcriber.transcribe()

    Returns:
        Dict of pattern results, each containing a score (0–100) and timestamps (seconds).
        e.g. {"scale_runs": {"score": 72.4, "timestamps": [4.2, 18.7]}, ...}
    """
    empty = {"score": 0.0, "timestamps": []}
    if not notes:
        return {
            "scale_runs":        empty,
            "arpeggios":         empty,
            "large_jumps":       empty,
            "repeated_notes":    empty,
            "chord_density":     empty,
            "hand_independence": empty,
        }

    tempo = _estimate_tempo(notes)

    results = {}
    for key, fn in [
        ("scale_runs",        _score_scale_runs),
        ("arpeggios",         _score_arpeggios),
        ("large_jumps",       _score_large_jumps),
        ("repeated_notes",    _score_repeated_notes),
        ("chord_density",     _score_chord_density),
        ("hand_independence", _score_hand_independence),
    ]:
        score, timestamps = fn(notes, tempo)
        results[key] = {"score": round(score, 1), "timestamps": timestamps}

    return results