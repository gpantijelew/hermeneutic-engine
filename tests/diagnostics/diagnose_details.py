import os
from pathlib import Path
from collections import Counter

def get_size(path):
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_size(entry.path)
    except OSError:
        pass
    return total

def format_size(size):
    return f"{size / (1024**3):.2f} GB"

def analyze_temp_content():
    temp_path = os.environ.get('TEMP')
    print(f"[*] Analysiere Inhalt von {temp_path}...")

    extensions = Counter()
    large_files = []

    try:
        # Nur die erste Ebene scannen, um schnell zu sein
        for entry in os.scandir(temp_path):
            if entry.is_file():
                ext = Path(entry.name).suffix.lower()
                extensions[ext] += 1
                if entry.stat().st_size > 50 * 1024 * 1024: # > 50MB
                    large_files.append((entry.name, entry.stat().st_size))
    except OSError as e:
        print(f"    Zugriffsfehler: {e}")

    print("    Häufigste Dateitypen (Top 5):")
    for ext, count in extensions.most_common(5):
        print(f"    -> {ext or 'Ohne Endung'}: {count} Dateien")

    if large_files:
        print("    Große Einzeldateien (>50MB):")
        for name, size in large_files[:5]:
            print(f"    -> {name}: {format_size(size)}")

def analyze_appdata_subdirs():
    local_appdata = os.environ.get('LOCALAPPDATA')
    print(f"\n[*] Analysiere Unterordner von {local_appdata}...")

    subdirs = []
    try:
        for entry in os.scandir(local_appdata):
            if entry.is_dir():
                # Wir schätzen die Größe (kann dauern, daher nur Top-Level)
                s = get_size(entry.path)
                if s > 1024**3: # Nur Ordner > 1GB anzeigen
                    subdirs.append((s, entry.name))
    except OSError:
        pass

    subdirs.sort(key=lambda x: x[0], reverse=True)

    for size, name in subdirs[:10]:
        print(f"    -> /{name}: {format_size(size)}")

if __name__ == "__main__":
    print("=== DETAIL DIAGNOSE ===\n")
    analyze_temp_content()
    analyze_appdata_subdirs()