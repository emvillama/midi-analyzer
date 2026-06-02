from backend.transcriber import transcribe
from backend.analyzer import analyze

notes = transcribe("temp/clairdelune.wav")
scores = analyze(notes)

for pattern, score in scores.items():
    print(f"{pattern:<20} {score}")