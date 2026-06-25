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
                e.g. {"scale_runs": {"score": 72.4, "timestamps": [4.2, 18.7]}, ...}

    Returns:
        List of recommendation dicts, sorted by score descending.
        e.g. [
            {"label": "Hand independence", "timestamps": [1.2, 8.4]},
            {"label": "Arpeggios",         "timestamps": [4.2, 18.7]},
        ]
    """
    recommendations = [
        {
            "label":      LABELS[pattern],
            "timestamps": scores[pattern]["timestamps"],
        }
        for pattern, entry in scores.items()
        if entry["score"] >= THRESHOLDS.get(pattern, 30.0)
    ]

    recommendations.sort(
        key=lambda r: scores[next(k for k, v in LABELS.items() if v == r["label"])]["score"],
        reverse=True,
    )

    return recommendations