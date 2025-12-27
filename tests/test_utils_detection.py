"""
Test-Script für utils.py v49.5 (Confidence-Score Edition)

Testet:
1. Wikisource-Detection mit Diagnostics
2. DeepSeek-Detection
3. Confidence-Scores für verschiedene HTML-Inputs
4. Edge-Cases (mehrdeutige Signaturen)
"""

import sys
import os

# Path-Fix
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)

# Import der aktualisierten utils
from modules.importers.utils import detect_platform, PLATFORM_MARKERS


def test_wikisource_detection():
    """Testet Wikisource-Detection mit verschiedenen Signaturen."""
    print("🧪 TEST 1: Wikisource-Detection")
    print("-" * 60)
    
    # Minimal-HTML (nur eine Signatur)
    minimal_html = b"""
    <html>
    <body>
        <div class="mw-parser-output">
            <p>Test-Content</p>
        </div>
    </body>
    </html>
    """
    
    platform, confidence, diagnostics = detect_platform(minimal_html)
    
    print(f"Minimal-HTML (1 Signatur):")
    print(f"  Platform: {platform}")
    print(f"  Confidence: {confidence:.2%}")
    print(f"  Gefundene Marker: {diagnostics.get(platform, [])}")
    
    # Full-HTML (alle Signaturen)
    full_html = b"""
    <html>
    <head>
        <meta name="generator" content="MediaWiki 1.40.0">
    </head>
    <body>
        <div id="mw-content-text">
            <div class="mw-parser-output">
                <span class="ws-noexport">Test</span>
            </div>
        </div>
    </body>
    </html>
    """
    
    platform, confidence, diagnostics = detect_platform(full_html)
    
    print(f"\nFull-HTML (4 Signaturen):")
    print(f"  Platform: {platform}")
    print(f"  Confidence: {confidence:.2%}")
    print(f"  Gefundene Marker: {diagnostics.get(platform, [])}")
    
    # Erwartung
    print(f"\n{'✅ PASS' if platform == 'wikisource' else '❌ FAIL'}")


def test_deepseek_detection():
    """Testet DeepSeek-Detection."""
    print("\n🧪 TEST 2: DeepSeek-Detection")
    print("-" * 60)
    
    deepseek_html = b"""
    <html>
    <body>
        <div class="ds-chat-container">
            <div class="ds-message-item">User message</div>
            <div class="ds-message-item">Model response</div>
        </div>
    </body>
    </html>
    """
    
    platform, confidence, diagnostics = detect_platform(deepseek_html)
    
    print(f"DeepSeek-HTML:")
    print(f"  Platform: {platform}")
    print(f"  Confidence: {confidence:.2%}")
    print(f"  Gefundene Marker: {diagnostics.get(platform, [])}")
    print(f"\n{'✅ PASS' if platform == 'deepseek' else '❌ FAIL'}")


def test_ambiguous_detection():
    """Testet mehrdeutige Signaturen (mehrere Plattformen möglich)."""
    print("\n🧪 TEST 3: Mehrdeutige Signaturen")
    print("-" * 60)
    
    # HTML mit Gemini UND ChatGPT-Signaturen (realistisch bei Copy-Paste)
    ambiguous_html = b"""
    <html>
    <body>
        <div class="message-box">Gemini Marker</div>
        <article data-testid="conversation-turn-1">ChatGPT Marker</article>
    </body>
    </html>
    """
    
    platform, confidence, diagnostics = detect_platform(ambiguous_html)
    
    print(f"Ambiguous HTML:")
    print(f"  Beste Match: {platform}")
    print(f"  Confidence: {confidence:.2%}")
    print(f"  Alle gefundenen Plattformen:")
    for p, markers in diagnostics.items():
        print(f"    - {p}: {markers} ({len(markers)} Marker)")
    
    # Erklärung
    print(f"\n💡 Die Plattform mit den meisten Treffern gewinnt.")


def test_unknown_platform():
    """Testet Verhalten bei unbekanntem HTML."""
    print("\n🧪 TEST 4: Unbekannte Plattform")
    print("-" * 60)
    
    unknown_html = b"""
    <html>
    <body>
        <p>Einfacher Text ohne erkennbare Signaturen</p>
    </body>
    </html>
    """
    
    platform, confidence, diagnostics = detect_platform(unknown_html)
    
    print(f"Unbekanntes HTML:")
    print(f"  Platform: {platform}")
    print(f"  Confidence: {confidence:.2%}")
    print(f"  Diagnostics: {diagnostics}")
    print(f"\n{'✅ PASS' if platform is None else '❌ FAIL'} (erwartet: None)")


def test_real_wikisource():
    """Testet mit echtem Wikisource-HTML (simuliert)."""
    print("\n🧪 TEST 5: Real-World Wikisource (Tynjanov)")
    print("-" * 60)
    
    # Simulierter Ausschnitt der echten Seite (mit UTF-8 Encoding)
    real_html_str = """
    <!DOCTYPE html>
    <html class="client-nojs vector-feature-limited-width-clientpref-1" lang="ru" dir="ltr">
    <head>
        <meta charset="UTF-8">
        <title>О литературной эволюции (Тынянов) — Викитека</title>
        <meta name="generator" content="MediaWiki 1.43.0">
    </head>
    <body class="skin-vector-2022">
        <div class="vector-page-titlebar">
            <h1 id="firstHeading" class="firstHeading mw-first-heading">
                О литературной эволюции (Тынянов)
            </h1>
        </div>
        <div id="mw-content-text" class="mw-body-content">
            <div class="mw-parser-output">
                <p><b>Борису Эйхенбауму</b></p>
                <p>1. Положение истории литературы...</p>
            </div>
        </div>
    </body>
    </html>
    """
    # Konvertiere zu Bytes (wie es die detect_platform() Funktion erwartet)
    real_html = real_html_str.encode('utf-8')
    
    platform, confidence, diagnostics = detect_platform(real_html)
    
    print(f"Tynjanov-Seite:")
    print(f"  Platform: {platform}")
    print(f"  Confidence: {confidence:.2%}")
    print(f"  Gefundene Marker: {diagnostics.get(platform, [])}")
    print(f"\n{'✅ PASS' if platform == 'wikisource' and confidence >= 0.5 else '❌ FAIL'}")


def main():
    print("=" * 60)
    print("🚀 UTILS.PY v49.5 TEST SUITE (Confidence-Score Edition)")
    print("=" * 60)
    print()
    
    try:
        test_wikisource_detection()
        test_deepseek_detection()
        test_ambiguous_detection()
        test_unknown_platform()
        test_real_wikisource()
        
        print("\n" + "=" * 60)
        print("🎉 ALLE TESTS ABGESCHLOSSEN!")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ FEHLER: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
