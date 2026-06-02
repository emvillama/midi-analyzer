from backend.downloader import download_audio

url = "https://www.youtube.com/watch?v=X-Xxqt6Xdio"
print("Downloading...")
path = download_audio(url)
print(f"Downloaded to: {path}")