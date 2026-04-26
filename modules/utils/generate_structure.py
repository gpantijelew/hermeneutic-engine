import os
from pathlib import Path

# Diese Ordner ignorieren wir, damit die Übersicht lesbar bleibt
IGNORE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "venv",
    "env",
    ".pytest_cache",
    "node_modules",
    "site-packages",
    "dist",
    "build",
    "egg-info",
}

# Diese Dateiendungen ignorieren wir (Binaries, Cache)
IGNORE_EXTS = {".pyc", ".pyd", ".obj", ".exe", ".dll", ".so", ".git"}


def generate_tree(start_path, output_file):
    start_path = Path(start_path).resolve()

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"Projektstruktur für: {start_path.name}\n")
        f.write("=" * 40 + "\n\n")

        for root, dirs, files in os.walk(start_path):
            # Verzeichnisse filtern (in-place, damit os.walk sie nicht betritt)
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            # Einrückung berechnen
            rel_path = Path(root).relative_to(start_path)
            if str(rel_path) == ".":
                level = 0
            else:
                level = len(rel_path.parts)

            indent = "    " * level

            # Ordnername schreiben
            if level == 0:
                f.write(f"{start_path.name}/\n")
            else:
                f.write(f"{indent}{rel_path.name}/\n")

            # Dateien schreiben
            sub_indent = "    " * (level + 1)
            for file in sorted(files):
                if not any(file.endswith(ext) for ext in IGNORE_EXTS):
                    f.write(f"{sub_indent}{file}\n")


if __name__ == "__main__":
    generate_tree(".", "struktur.txt")
    print("[OK] struktur.txt wurde erfolgreich erstellt (ohne venv/git Müll).")
