from backend.transcriber import transcribe

notes = transcribe("temp/YOUR_VIDEO_ID.wav")
print(f"Total notes: {len(notes)}")
for n in notes[:10]:
    print(n)