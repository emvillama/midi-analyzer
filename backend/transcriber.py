import os
import tempfile
import pretty_midi
from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH


def transcribe(wav_path: str) -> list[dict]:
    """
    Convert a .wav file to a list of MIDI notes using basic-pitch.

    Args:
        wav_path: Path to the .wav file (e.g. "temp/abc123.wav")

    Returns:
        List of note dicts:
        [
            {"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80},
            ...
        ]
        pitch is MIDI note number (0–127, middle C = 60)
        start/end are in seconds
        velocity is 0–127

    Side effect: also writes a standard .mid file next to the wav (same
    basename, .mid extension) — e.g. "temp/abc123.wav" -> "temp/abc123.mid".
    This is what powers the visual tutorial view (served via /midi/{video_id}
    and rendered client-side with html-midi-player) — it's a real MIDI file,
    not a re-encoding of the note dicts, so it round-trips tempo/instrument
    info that the flat note list above doesn't carry.
    """
    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"Audio file not found: {wav_path}")

    # Run basic-pitch transcription
    try:
        model_output, midi_data, note_events = predict(
            wav_path,
            ICASSP_2022_MODEL_PATH,
        )
    except Exception as e:
        raise RuntimeError(
            f"Transcription failed for {wav_path}: {e}"
        ) from e

    # midi_data is a pretty_midi.PrettyMIDI object — extract notes directly.
    # pretty_midi returns pitch/velocity as numpy scalar types (e.g.
    # numpy.int64), which FastAPI's JSON encoder can't serialize — cast
    # everything to native Python types.
    notes = []
    for instrument in midi_data.instruments:
        for note in instrument.notes:
            notes.append({
                "pitch": int(note.pitch),
                "start": round(float(note.start), 4),
                "end": round(float(note.end), 4),
                "velocity": int(note.velocity),
            })

    # Sort by start time
    notes.sort(key=lambda n: n["start"])

    # Persist the actual MIDI file for the visual tutorial view. Non-fatal
    # if this fails for some reason (disk full, permissions) — the rest of
    # the pipeline (analysis, recommendations) doesn't depend on it, only
    # the tutorial view does, and that degrades gracefully client-side.
    try:
        midi_path = os.path.splitext(wav_path)[0] + ".mid"
        midi_data.write(midi_path)
    except Exception:
        pass

    return notes