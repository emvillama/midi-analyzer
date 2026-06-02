from backend.transcriber import transcribe
from backend.analyzer import analyze
from backend.recommender import recommend

notes = transcribe("temp/clairdelune.wav")
scores = analyze(notes)
recs = recommend(scores)

print("Recommended practice:")
for r in recs:
    print(f"  - {r}")