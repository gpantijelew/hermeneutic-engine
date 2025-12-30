import os
import time
from pathlib import Path
import datetime

def get_dir_size_and_age(path_str):
    path = Path(path_str).resolve()
    if not path.exists():
        return 0, None, 0

    total_size = 0
    newest_mtime = 0
    file_count = 0

    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    stat = os.stat(fp)
                    total_size += stat.st_size
                    if stat.st_mtime > newest_mtime:
                        newest_mtime = stat.st_mtime
                    file_count += 1
                except OSError:
                    pass
    except OSError:
        pass # Permission denied

    return total_size, newest_mtime, file_count

def format_size(size):
    return f"{size / (1024**3):.2f} GB"

def format_date(timestamp):
    if timestamp == 0: return "Nie"
    return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')

def inspect_location(name, path_str):
    print(f"[*] Prüfe: {name}")
    print(f"    Pfad: {path_str}")

    size, mtime, count = get_dir_size_and_age(path_str)

    print(f"    Größe: {format_size(size)}")
    print(f"    Dateien: {count}")
    print(f"    Neueste Änderung: {format_date(mtime)}")

    # Warnung wenn sehr neu (letzte 24h) und groß (> 1GB)
    is_recent = (time.time() - mtime) < 86400 # 24h
    if is_recent and size > 1024**3:
        print("    !!! ALARM: Hier wurde in den letzten 24h massiv geschrieben!")

    print("-" * 40)

if __name__ == "__main__":
    print("=== WINDOWS SYSTEM DIAGNOSE ===\n")

    user_profile = os.environ.get('USERPROFILE')

    # 1. HuggingFace (Prüfen ob wirklich alt)
    hf_path = os.path.join(user_profile, ".cache", "huggingface")
    inspect_location("HuggingFace Cache", hf_path)

    # 2. Windows Temp (Der übliche Verdächtige für Python Skripte)
    # Python tempfile.gettempdir() landet meist hier
    temp_path = os.environ.get('TEMP')
    inspect_location("Windows Temp (%TEMP%)", temp_path)

    # 3. GCloud Config & Logs
    # Unter Windows meist in AppData\Roaming\gcloud
    appdata = os.environ.get('APPDATA') # Roaming
    gcloud_path = os.path.join(appdata, "gcloud")
    inspect_location("Google Cloud SDK Config/Logs", gcloud_path)

    # 4. Local AppData GCloud (manchmal Cache)
    local_appdata = os.environ.get('LOCALAPPDATA')
    inspect_location("Local AppData", local_appdata)
