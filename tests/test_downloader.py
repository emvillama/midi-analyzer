from backend.downloader import download_audio

url = "https://www.youtube.com/watch?v=cVYH-7QGE-A"
print("Downloading...")
path = download_audio(url)
print(f"Downloaded to: {path}")