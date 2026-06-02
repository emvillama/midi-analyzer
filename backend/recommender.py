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


def recommend(scores: dict[str, float]) -> list[str]:
    """
    Map pattern scores to a practice recommendation list.

    Args:
        scores: Output from analyzer.analyze()

    Returns:
        List of recommendation strings, sorted by score descending.
        e.g. ["Hand independence", "Chord playing", "Arpeggios"]
    """
    recommendations = [
        LABELS[pattern]
        for pattern, score in scores.items()
        if score >= THRESHOLDS.get(pattern, 30.0)
    ]

    # Sort by score descending so highest-priority items appear first
    recommendations.sort(key=lambda label: scores[
        next(k for k, v in LABELS.items() if v == label)
    ], reverse=True)

    return recommendations