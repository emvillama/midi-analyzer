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
    """
    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"Audio file not found: {wav_path}")

    # Run basic-pitch transcription
    model_output, midi_data, note_events = predict(
        wav_path,
        ICASSP_2022_MODEL_PATH,
    )

    # midi_data is a pretty_midi.PrettyMIDI object — extract notes directly
    notes = []
    for instrument in midi_data.instruments:
        for note in instrument.notes:
            notes.append({
                "pitch": note.pitch,
                "start": round(note.start, 4),
                "end": round(note.end, 4),
                "velocity": note.velocity,
            })

    # Sort by start time
    notes.sort(key=lambda n: n["start"])

    return notes