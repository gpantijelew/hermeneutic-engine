# html_spy.py
import sys
import os
from bs4 import BeautifulSoup

def spy_on_html(file_path):
    if not os.path.exists(file_path):
        print(f"❌ Datei nicht gefunden: {file_path}")
        return

    print(f"🕵️  Untersuche Datei: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            soup = BeautifulSoup(content, 'html.parser')

        print(f"📄 Dateigröße: {len(content)} Bytes")

        # 1. Suche nach DeepSeek (ds-*)
        ds_items = soup.find_all(class_=lambda x: x and 'ds-' in x)
        if ds_items:
            print(f"\n✅ DeepSeek-Verdacht! {len(ds_items)} Elemente mit 'ds-' Klasse.")
            print("Erstes Element Struktur:")
            print(ds_items[0].prettify()[:1000])

        # 2. Suche nach Kimi (chat-*)
        kimi_items = soup.find_all(class_=lambda x: x and 'chat-' in x)
        if kimi_items:
            print(f"\n✅ Kimi-Verdacht! {len(kimi_items)} Elemente mit 'chat-' Klasse.")
            print("Erstes Element Struktur:")
            print(kimi_items[0].prettify()[:1000])

        # 3. Generische Analyse (Die ersten 3 tiefen Divs)
        print("\n--- GENERISCHE STRUKTUR (Erste 2000 Zeichen Body) ---")
        if soup.body:
            print(soup.body.prettify()[:2000])
        else:
            print(soup.prettify()[:2000])

    except Exception as e:
        print(f"❌ Fehler beim Lesen: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("⚠️ Bitte Datei angeben: python html_spy.py <pfad_zur_html>")
        print("Beispiel: python html_spy.py uploads/kimi_export.html")
    else:
        spy_on_html(sys.argv[1])