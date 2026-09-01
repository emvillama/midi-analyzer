import os


def get_app_data_dir() -> str:
    """
    A genuinely persistent, OS-appropriate directory for this app's data.

    Unlike a PyInstaller onefile build's bundled `temp/` — which resolves
    relative to the extracted bundle and lives inside the ephemeral
    per-launch extraction folder (wiped when the app closes) — this
    directory survives app restarts, updates, and reinstalls.

    Windows: %APPDATA%\\midi-analyzer
    Linux/macOS: $XDG_DATA_HOME/midi-analyzer or ~/.local/share/midi-analyzer
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

    path = os.path.join(base, "midi-analyzer")
    os.makedirs(path, exist_ok=True)
    return path