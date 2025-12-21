import os
import sys
try:
    from pypdf import PdfReader
except ImportError:
    print("⚠️ pypdf fehlt. Installiere es mit: pip install pypdf")
    sys.exit(1)

def analyze_pdfs(directory):
    print(f"🔍 Untersuche PDFs in: {directory}")

    files = [f for f in os.listdir(directory) if f.lower().endswith('.pdf')]
    if not files:
        print("❌ Keine PDF-Dateien gefunden.")
        return

    print(f"📂 Gefunden: {len(files)} Dateien.\n")

    for filename in files:
        filepath = os.path.join(directory, filename)
        print(f"--- Prüfe: {filename} ---")

        try:
            reader = PdfReader(filepath)

            # 1. Verschlüsselung checken
            if reader.is_encrypted:
                print("   ❌ FEHLER: Datei ist verschlüsselt/passwortgeschützt.")
                continue

            # 2. Seiten und Text checken
            num_pages = len(reader.pages)
            print(f"   📄 Seiten: {num_pages}")

            total_text = ""
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    total_text += text

            char_count = len(total_text.strip())

            if char_count == 0:
                print("   ⚠️ WARNUNG: 0 Zeichen extrahiert. (Vermutlich Bild-Scan ohne OCR?)")
            else:
                print(f"   ✅ OK: {char_count} Zeichen extrahiert.")
                print(f"   📝 Vorschau: {total_text[:100].replace(chr(10), ' ')}...")

        except Exception as e:
            print(f"   ❌ CRASH: {str(e)}")

        print("")

if __name__ == "__main__":
    # Hier den Pfad zu dem Ordner eintragen, wo deine 4 PDFs liegen
    # Wenn sie im Hauptordner liegen, einfach '.' lassen
    target_dir = "." 

    if len(sys.argv) > 1:
        target_dir = sys.argv[1]

    analyze_pdfs(target_dir)