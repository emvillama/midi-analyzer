from collections import defaultdict

# ── section-building tuning ──────────────────────────────────────────────────
#
# Detectors below no longer return single-point timestamps — they return the
# actual (start, end) span of each qualifying occurrence, taken directly from
# the notes involved (e.g. a scale run's span is its first note's start to
# its last note's end). Those spans are then merged into practice-able
# "sections" using tempo-relative timing (beats, not a fixed number of
# seconds), so the notion of "nearby" scales sensibly with how fast the
# piece actually is, and every section is padded slightly and guaranteed a
# practical minimum length — a genuinely unpracticeable 1-second sliver is
# never returned on its own.

SECTION_GAP_BEATS = 2.0     # merge occurrences within this many beats of each other
SECTION_MIN_SECONDS = 3.0   # absolute floor on a section's length
SECTION_MIN_BEATS = 4.0     # tempo-relative floor on a section's length
SECTION_PAD_BEATS = 0.5     # lead-in/lead-out padding added to each section
SECTION_MAX_SECONDS = 20.0  # a pattern that runs continuously through the whole
                             # piece would otherwise merge into one giant,
                             # unpracticeable "section" — cap it and split

# Even after merging, a piece saturated with a pattern throughout could still
# produce a long list. Cap it so the UI stays usable — earliest occurrences
# are generally the most useful to see first.
MAX_SECTIONS = 15

# helpers ──────────────────────────────────────────────────────────

def _cluster_events(events: list[tuple[float, float]], gap_threshold: float) -> list[list[tuple[float, float]]]:
    """Group events (sorted by start) into clusters where each consecutive
    pair is within `gap_threshold` seconds of each other."""
    ordered = sorted(events, key=lambda e: e[0])
    clusters = [[ordered[0]]]
    for ev in ordered[1:]:
        if ev[0] - clusters[-1][-1][1] <= gap_threshold:
            clusters[-1].append(ev)
        else:
            clusters.append([ev])
    return clusters


def _split_long_cluster(
    cluster: list[tuple[float, float]], max_duration: float, min_gap_for_split: float
) -> list[list[tuple[float, float]]]:
    """
    If a cluster's overall span exceeds `max_duration`, split it into
    smaller sub-clusters — but only at internal gaps at least as large as
    `min_gap_for_split` (the same tempo-relative threshold used to form
    clusters in the first place). Cutting at a gap smaller than that isn't
    a real break in the pattern, just an arbitrary chop for length's sake
    — and those arbitrary fragments tend to overlap each other once each
    is independently padded/stretched. If no internal gap is actually
    significant, the pattern genuinely is continuous throughout, and a
    longer section is a more honest result than fabricated fragments.
    """
    span = cluster[-1][1] - cluster[0][0]
    if span <= max_duration or len(cluster) < 2:
        return [cluster]

    candidate_gaps = sorted(
        (
            (cluster[i + 1][0] - cluster[i][1], i)
            for i in range(len(cluster) - 1)
            if cluster[i + 1][0] - cluster[i][1] >= min_gap_for_split
        ),
        reverse=True,
    )
    if not candidate_gaps:
        return [cluster]

    def segments_for(cuts: set[int]) -> list[list[tuple[float, float]]]:
        starts = [0] + [c + 1 for c in sorted(cuts)]
        ends = [c for c in sorted(cuts)] + [len(cluster) - 1]
        return [cluster[s:e + 1] for s, e in zip(starts, ends)]

    cut_indices: set[int] = set()
    for _, idx in candidate_gaps:
        cut_indices.add(idx)
        segments = segments_for(cut_indices)
        if all(seg[-1][1] - seg[0][0] <= max_duration for seg in segments):
            return segments

    # Used every gap large enough to be meaningful but still couldn't get
    # every segment under the cap — return the best effort achieved using
    # only genuine pauses, rather than resorting to arbitrary micro-cuts.
    return segments_for(cut_indices)


def _coalesce_overlapping_sections(sections: list[dict]) -> list[dict]:
    """
    Merge sections whose final (padded/stretched) ranges overlap. This can
    happen when a long run gets split into several short sub-segments that
    are each independently stretched to the minimum practice length,
    causing neighbors to overlap — this cleans up the resulting redundancy.
    """
    if not sections:
        return []
    ordered = sorted(sections, key=lambda s: s["start"])
    merged = [dict(ordered[0])]
    for s in ordered[1:]:
        if s["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], s["end"])
        else:
            merged.append(dict(s))
    return merged


def _merge_events_into_sections(
    events: list[tuple[float, float]],
    tempo: float,
    gap_beats: float = SECTION_GAP_BEATS,
    min_duration_seconds: float = SECTION_MIN_SECONDS,
    min_duration_beats: float = SECTION_MIN_BEATS,
    pad_beats: float = SECTION_PAD_BEATS,
    max_duration_seconds: float = SECTION_MAX_SECONDS,
) -> list[dict]:
    """
    Merge individual (start, end) occurrences into practice-able sections.

    Occurrences within `gap_beats` of musical time of each other (scaled by
    tempo, not a fixed number of seconds) are merged into one section
    spanning from the first occurrence's start to the last occurrence's end
    — i.e. the section boundary follows where the pattern actually starts
    and stops happening in the music, not an arbitrary time window.

    A merged run longer than `max_duration_seconds` (e.g. a pattern that's
    genuinely continuous through much of the piece) is split at its largest
    internal gaps rather than left as one unpracticeable mega-section.

    Every returned section is padded slightly on both sides (a moment to
    prepare before the passage starts) and stretched to a practical minimum
    length if needed, so a genuinely tiny, unpracticeable sliver is never
    returned on its own.
    """
    if not events:
        return []

    beat_duration = 60.0 / tempo if tempo > 0 else 0.5
    gap_threshold = gap_beats * beat_duration
    min_duration = max(min_duration_seconds, min_duration_beats * beat_duration)
    pad = pad_beats * beat_duration

    clusters = _cluster_events(events, gap_threshold)

    sections = []
    for cluster in clusters:
        for segment in _split_long_cluster(cluster, max_duration_seconds, gap_threshold):
            start = segment[0][0]
            end = max(e[1] for e in segment)
            start = max(0.0, start - pad)
            end = end + pad
            if end - start < min_duration:
                deficit = min_duration - (end - start)
                start = max(0.0, start - deficit / 2)
                end = start + min_duration
            sections.append({"start": round(start, 2), "end": round(end, 2)})

    return _coalesce_overlapping_sections(sections)


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
# Each returns (score, events) where events is a list of (start, end) spans
# — the actual musical extent of each qualifying occurrence, not a single
# point in time.

def _score_scale_runs(notes: list[dict], tempo: float) -> tuple[float, list[tuple[float, float]]]:
    """Stepwise melodic motion: intervals of 1–2 semitones, 4+ consecutive notes."""
    if len(notes) < 4:
        return 0.0, []

    groups = _group_simultaneous(notes)
    melody = [min(g, key=lambda n: n["pitch"]) for g in groups if len(g) == 1]

    if len(melody) < 4:
        return 0.0, []

    run_lengths = []
    events = []
    run = 1
    run_start_idx = 0
    for i in range(1, len(melody)):
        interval = abs(melody[i]["pitch"] - melody[i-1]["pitch"])
        if 1 <= interval <= 2:
            run += 1
        else:
            if run >= 4:
                run_lengths.append(run)
                events.append((melody[run_start_idx]["start"], melody[i-1]["end"]))
            run = 1
            run_start_idx = i
    if run >= 4:
        run_lengths.append(run)
        events.append((melody[run_start_idx]["start"], melody[-1]["end"]))

    if not run_lengths:
        return 0.0, []

    total_stepwise = sum(run_lengths)
    ratio = total_stepwise / max(len(melody), 1)
    raw = min(ratio * 150, 100)
    return min(raw * _tempo_weight(tempo), 100), events


def _score_arpeggios(notes: list[dict], tempo: float) -> tuple[float, list[tuple[float, float]]]:
    """Broken chord tones: intervals of 3–7 semitones, non-simultaneous, directional."""
    groups = _group_simultaneous(notes)
    melody = [g[0] for g in groups if len(g) == 1]

    if len(melody) < 3:
        return 0.0, []

    arp_count = 0
    events = []
    run = 1
    last_dir = None
    run_start_idx = 0
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
                    events.append((melody[run_start_idx]["start"], melody[i-1]["end"]))
                run = 1
                last_dir = direction
                run_start_idx = i
        else:
            if run >= 3:
                arp_count += run
                events.append((melody[run_start_idx]["start"], melody[i-1]["end"]))
            run = 1
            last_dir = None
            run_start_idx = i
    if run >= 3:
        arp_count += run
        events.append((melody[run_start_idx]["start"], melody[-1]["end"]))

    ratio = arp_count / max(len(melody), 1)
    raw = min(ratio * 200, 100)
    return min(raw * _tempo_weight(tempo), 100), events


def _score_large_jumps(notes: list[dict], tempo: float) -> tuple[float, list[tuple[float, float]]]:
    """Intervals larger than a minor 6th (8 semitones) between consecutive melody notes."""
    groups = _group_simultaneous(notes)
    melody = [g[0] for g in groups]

    if len(melody) < 2:
        return 0.0, []

    events = []
    jump_count = 0
    for i in range(1, len(melody)):
        if abs(melody[i]["pitch"] - melody[i-1]["pitch"]) > 8:
            jump_count += 1
            # The jump's "extent" is the motion itself: from where the hand
            # was to where it lands.
            events.append((melody[i-1]["start"], melody[i]["end"]))

    ratio = jump_count / max(len(melody), 1)
    raw = min(ratio * 300, 100)
    return min(raw * _tempo_weight(tempo), 100), events


def _score_repeated_notes(notes: list[dict], tempo: float) -> tuple[float, list[tuple[float, float]]]:
    """Same pitch repeated within a short time window (< 0.5s)."""
    if len(notes) < 2:
        return 0.0, []

    sorted_notes = sorted(notes, key=lambda n: n["start"])
    events = []
    repeat_count = 0
    for i in range(1, len(sorted_notes)):
        if (sorted_notes[i]["pitch"] == sorted_notes[i-1]["pitch"]
                and (sorted_notes[i]["start"] - sorted_notes[i-1]["start"]) < 0.5):
            repeat_count += 1
            events.append((sorted_notes[i-1]["start"], sorted_notes[i]["end"]))

    ratio = repeat_count / max(len(sorted_notes), 1)
    raw = min(ratio * 300, 100)
    return min(raw * _tempo_weight(tempo), 100), events


def _score_chord_density(notes: list[dict], tempo: float) -> tuple[float, list[tuple[float, float]]]:
    """Average number of simultaneous notes per group."""
    groups = _group_simultaneous(notes)
    if not groups:
        return 0.0, []

    chord_groups = [g for g in groups if len(g) >= 3]
    events = [(g[0]["start"], max(n["end"] for n in g)) for g in chord_groups]
    ratio = len(chord_groups) / max(len(groups), 1)
    raw = min(ratio * 200, 100)
    return min(raw * _tempo_weight(tempo), 100), events


def _score_hand_independence(notes: list[dict], tempo: float) -> tuple[float, list[tuple[float, float]]]:
    """
    Proxy: simultaneous notes spanning a wide pitch range (> 12 semitones),
    suggesting left and right hand are doing different things.
    """
    groups = _group_simultaneous(notes)
    wide_groups = [
        g for g in groups
        if len(g) >= 2 and (max(n["pitch"] for n in g) - min(n["pitch"] for n in g)) > 12
    ]

    events = [(g[0]["start"], max(n["end"] for n in g)) for g in wide_groups]
    ratio = len(wide_groups) / max(len(groups), 1)
    raw = min(ratio * 200, 100)
    return min(raw * _tempo_weight(tempo), 100), events


# API ──────────────────────────────────────────────────────────

def analyze(notes: list[dict]) -> dict[str, dict]:
    """
    Run all pattern detectors on a list of MIDI notes.

    Args:
        notes: Output from transcriber.transcribe()

    Returns:
        Dict of pattern results, each containing a score (0–100) and a list
        of practice sections, each with a start/end time in seconds.
        e.g. {"scale_runs": {"score": 72.4, "sections": [{"start": 4.2, "end": 7.8}]}, ...}
    """
    empty = {"score": 0.0, "sections": []}
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
        score, events = fn(notes, tempo)
        sections = _merge_events_into_sections(events, tempo)[:MAX_SECTIONS]
        results[key] = {"score": round(score, 1), "sections": sections}

    return results