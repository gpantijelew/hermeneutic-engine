# inspect_artifacts.py
from bs4 import BeautifulSoup
import sys
import os

def spy_artifacts(file_path):
    if not os.path.exists(file_path):
        print("Datei nicht gefunden.")
        return

    print(f"🕵️  Untersuche Artefakte in: {file_path}")
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # 1. Suche nach Code-Blöcken (Standard Artefakte)
    code_blocks = soup.find_all(['pre', 'code'])
    print(f"\n📊 Gefundene Code-Blöcke (<pre>/<code>): {len(code_blocks)}")

    if code_blocks:
        print("   Beispiel (Erste 100 Zeichen):")
        print(f"   '{code_blocks[0].get_text()[:100]}...'")

    # 2. Suche nach spezifischen Claude-Artefakt-Klassen
    # Oft heißen sie "artifact", "code-block-wrapper" oder ähnlich
    artifact_candidates = soup.find_all(class_=lambda x: x and ('artifact' in x.lower() or 'code' in x.lower()))

    print(f"\n📊 Verdächtige Artefakt-Container: {len(artifact_candidates)}")
    if artifact_candidates:
        first = artifact_candidates[0]
        print(f"   Klasse: {first.get('class')}")
        print(f"   Inhalt (Preview): '{first.get_text()[:100]}...'")

    # 3. Prüfen, ob Artefakte im normalen Textfluss sind
    # Wir nehmen eine Model-Antwort und schauen rein
    responses = soup.find_all(class_="font-claude-response")
    if responses:
        print(f"\n📊 Prüfe eine Claude-Antwort auf Code...")
        sample = responses[0]
        if sample.find('pre') or sample.find('code'):
            print("✅ JA: Code-Tags sind INNERHALB der Nachrichten-Container.")
            print("   -> Der Importer sollte sie automatisch erfassen.")
        else:
            print("⚠️ NEIN: Keine Code-Tags in der ersten Antwort gefunden.")
            print("   (Das ist okay, wenn die erste Antwort keinen Code enthielt).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Bitte Datei angeben.")
    else:
        spy_artifacts(sys.argv[1])