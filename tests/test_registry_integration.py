"""
Test-Script für Importer-Registry (v49.5)

Testet:
1. Wikisource-Importer ist registriert
2. Auto-Detection funktioniert
3. PDF-Importer ist aktualisiert
4. Registry-Funktionen (list_platforms, get_importer, etc.)

Usage:
    python test_registry_integration.py
"""

import sys
import os

# Path-Fix (falls direkt ausgeführt)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, PROJECT_ROOT)

from modules.importers import (
    list_platforms, 
    get_importer, 
    is_experimental,
    get_platform_info,
    detect_platform
)


def test_registry():
    """Testet die Importer-Registry."""
    print("🧪 TEST 1: Registry-Funktionen")
    print("-" * 50)
    
    # 1. Liste alle Plattformen
    platforms = list_platforms()
    print(f"✅ {len(platforms)} Plattformen registriert:")
    for p in platforms:
        status = "🧪 EXPERIMENTAL" if is_experimental(p) else "✅ STABLE"
        print(f"   - {p}: {status}")
    
    # 2. Prüfe, ob Wikisource dabei ist
    print("\n🧪 TEST 2: Wikisource-Integration")
    print("-" * 50)
    
    if 'wikisource' in platforms:
        print("✅ Wikisource ist registriert!")
        
        # Hole Metadaten
        info = get_platform_info('wikisource')
        print(f"   Name: {info['name']}")
        print(f"   Formate: {info['formats']}")
        print(f"   Experimental: {info['experimental']}")
        print(f"   Beschreibung: {info['description']}")
        
        # Teste Instanziierung
        try:
            importer = get_importer('wikisource')
            print(f"✅ Wikisource-Importer instanziiert: {importer.platform_name}")
        except Exception as e:
            print(f"❌ Fehler beim Instanziieren: {e}")
    else:
        print("❌ Wikisource NICHT registriert!")
    
    # 3. Prüfe PDF-Importer
    print("\n🧪 TEST 3: PDF-Importer (v49.5)")
    print("-" * 50)
    
    if 'pdf' in platforms:
        print("✅ PDF-Importer ist registriert!")
        info = get_platform_info('pdf')
        print(f"   Beschreibung: {info['description']}")
        
        # Prüfe, ob es die neue Version ist
        if 'v49.5' in info['description'] or 'verbesserte' in info['description']:
            print("✅ PDF-Importer ist auf v49.5 aktualisiert!")
        else:
            print("⚠️ PDF-Importer könnte noch alte Version sein")
    else:
        print("❌ PDF-Importer NICHT registriert!")


def test_auto_detection():
    """Testet die Auto-Detection mit Beispiel-HTML."""
    print("\n🧪 TEST 4: Auto-Detection")
    print("-" * 50)
    
    # Wikisource-HTML (simuliert)
    wikisource_html = b"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="generator" content="MediaWiki 1.40.0">
    </head>
    <body>
        <div class="mw-parser-output">
            <p>Test-Content</p>
        </div>
    </body>
    </html>
    """
    
    # ChatGPT-HTML (simuliert)
    chatgpt_html = b"""
    <!DOCTYPE html>
    <html>
    <body>
        <article data-testid="conversation-turn-1">
            <div data-message-author-role="user">Test</div>
        </article>
    </body>
    </html>
    """
    
    # Teste Detection
    wikisource_detected = detect_platform(wikisource_html)
    chatgpt_detected = detect_platform(chatgpt_html)
    
    print(f"Wikisource HTML → Erkannt als: {wikisource_detected}")
    print(f"   {'✅ KORREKT' if wikisource_detected == 'wikisource' else '❌ FALSCH'}")
    
    print(f"ChatGPT HTML → Erkannt als: {chatgpt_detected}")
    print(f"   {'✅ KORREKT' if chatgpt_detected == 'chatgpt' else '❌ FALSCH'}")


def main():
    """Führt alle Tests aus."""
    print("=" * 50)
    print("🚀 IMPORTER-REGISTRY INTEGRATION TEST (v49.5)")
    print("=" * 50)
    print()
    
    try:
        test_registry()
        test_auto_detection()
        
        print("\n" + "=" * 50)
        print("🎉 ALLE TESTS ABGESCHLOSSEN!")
        print("=" * 50)
    
    except Exception as e:
        print(f"\n❌ FEHLER: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()