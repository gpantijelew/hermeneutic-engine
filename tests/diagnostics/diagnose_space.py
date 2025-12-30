import os
from pathlib import Path

def get_size(start_path = '.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                try:
                    total_size += os.path.getsize(fp)
                except OSError:
                    pass # Permission errors or file vanished
    return total_size

def format_size(size_bytes):
    if size_bytes == 0: return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(0)
    p = 1024
    import math
    if size_bytes > 0:
        i = int(math.floor(math.log(size_bytes, p)))
    s = round(size_bytes / (p ** i), 2)
    return "%s %s" % (s, size_name[i])

def analyze_directory(path_str, label):
    path = Path(path_str).resolve()
    if not path.exists():
        print(f"[-] {label}: Pfad nicht gefunden ({path})")
        return

    print(f"[*] Analysiere {label}...")
    total = get_size(path)
    print(f"    Gesamtgröße: {format_size(total)}")

    # Top 5 Unterordner
    subdirs = []
    for item in path.iterdir():
        if item.is_dir():
            s = get_size(item)
            subdirs.append((s, item.name))
        elif item.is_file():
            # Check for massive single files (like logs)
            if item.stat().st_size > 100 * 1024 * 1024: # > 100MB
                print(f"    ! WARNUNG: Große Datei gefunden: {item.name} ({format_size(item.stat().st_size)})")

    subdirs.sort(key=lambda x: x[0], reverse=True)

    for size, name in subdirs[:5]:
        print(f"    -> /{name}: {format_size(size)}")
    print("-" * 40)

if __name__ == "__main__":
    print("=== SPEICHERPLATZ DIAGNOSE (v47.2) ===\n")

    # 1. Projektverzeichnis (ChromaDB, Logs, venv)
    analyze_directory(".", "Projekt-Root")

    # 2. HuggingFace Cache (Standardort)
    home = Path.home()
    hf_cache = home / ".cache" / "huggingface"
    analyze_directory(hf_cache, "HuggingFace Cache (Global)")

    # 3. Temp Ordner (System)
    # Optional, falls wir Tempfiles leaken
    # analyze_directory("/tmp", "System Temp") 