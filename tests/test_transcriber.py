from backend.transcriber import transcribe

notes = transcribe("temp/cVYH-7QGE-A.wav")
print(f"Total notes: {len(notes)}")
for n in notes[:10]:
    print(n)