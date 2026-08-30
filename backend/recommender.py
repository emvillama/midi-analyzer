# Pattern thresholds for recommendation
THRESHOLDS = {
    "scale_runs":        30.0,
    "arpeggios":         30.0,
    "large_jumps":       30.0,
    "repeated_notes":    30.0,
    "chord_density":     40.0,
    "hand_independence": 40.0,
}

# Label formatting
LABELS = {
    "scale_runs":        "Scales",
    "arpeggios":         "Arpeggios",
    "large_jumps":       "Large jumps / position shifts",
    "repeated_notes":    "Repeated notes",
    "chord_density":     "Chord playing",
    "hand_independence": "Hand independence",
}


def recommend(scores: dict[str, dict]) -> list[dict]:
    """
    Map pattern scores to a practice recommendation list.

    Args:
        scores: Output from analyzer.analyze()
                e.g. {"scale_runs": {"score": 72.4, "sections": [{"start": 4.2, "end": 7.8}]}, ...}

    Returns:
        List of recommendation dicts, sorted by score descending.
        e.g. [
            {"label": "Hand independence", "sections": [{"start": 1.2, "end": 5.6}]},
            {"label": "Arpeggios",         "sections": [{"start": 4.2, "end": 7.8}]},
        ]
    """
    qualifying = [
        (pattern, entry)
        for pattern, entry in scores.items()
        if entry["score"] >= THRESHOLDS.get(pattern, 30.0)
    ]

    qualifying.sort(key=lambda item: item[1]["score"], reverse=True)

    return [
        {
            "label":    LABELS[pattern],
            "sections": entry["sections"],
        }
        for pattern, entry in qualifying
    ]