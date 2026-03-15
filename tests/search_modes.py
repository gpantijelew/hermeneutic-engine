import os

search_terms = ['analytical', 'factual']
exclude_dirs = ['.git', '__pycache__', 'venv', 'env']

print("🔍 Starte Diagnose: Suche nach 'analytical' und 'factual' im Code...\n")

for root, dirs, files in os.walk('.'):
    # Ignoriere irrelevante Ordner
    dirs[:] = [d for d in dirs if d not in exclude_dirs]

    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        line_lower = line.lower()
                        if any(term in line_lower for term in search_terms):
                            # Ausgabe formatieren für gute Lesbarkeit
                            print(f"[{filepath}] Zeile {line_num}:")
                            print(f"    {line.strip()}\n")
            except Exception as e:
                print(f"⚠️ Fehler beim Lesen von {filepath}: {e}")

print("✅ Diagnose beendet.")