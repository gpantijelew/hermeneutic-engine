# modules/text_analyzer.py — v59.9.1: B13b-Leerzeilen-Fix + Autoren-Erkennung
"""
STILISTIC LAB — Etappe 1: Deterministische Textanalyse.

ARCHITEKTUR-ENTSCHEIDUNG (v57.4):
LLMs können Zählen und Charakterisieren nicht simultan leisten.
"Zähle Hauptsätze" wird als Anregung verarbeitet, nicht als Befehl.
Deshalb: Python zählt, LLM charakterisiert auf Faktenbasis.

LEKTIONEN AUS AGENTS.md:
- "Morphologische Komplexität" misst Wortlänge+Fremdwort, nicht Tynjanows
  "hohe lexikalische Färbung". Proxy wird ehrlich benannt.
- Hotspot-Sätze statt "erste 1500 Zeichen": Python identifiziert
  auffälligste Sätze → relevante Ausschnitte für Etappe 2+3.

v59.9 CHANGES (D1–D6):
- D1: _GR_FUNC_NORMALIZED massiv erweitert — Kopula-Formen (ἦεν, ἦν, ἔστι,
  εἰμί etc.), Quantorpronomina (πάντες, πάντα, πᾶσι etc.), enklitische
  Partikel ἄρ, Demonstrativpronomina (αὐτός etc.). Vorher: ἦεν erschien
  als „häufigstes Inhaltswort" (3x!), πάνtes ebenfalls. Jetzt: echte Lexik.
- D2: _detect_greek_stanzas() — Kontinuierlicher Hexameter (keine Leer-
  zeilen) wird jetzt wie russische Übersetzungen behandelt: Jeder Vers = 1
  Strophe. Vorher: „Strophen: 1 (94)". Jetzt: „Strophen: 94 (1-1-1-...)".
- D3: Funktionswort-Bigramme gefiltert — „μὲν ἄρ" (zwei Partikel) wird
  nicht mehr als semantisches Bigramm angezeigt. Nur Bigramme mit mind.
  einem Inhaltswort werden gezeigt.
- D4: Russische Komposita-Präfixe erweitert — 30 produktive Adverb-о-
  Verbindungselemente (темно-, пышно-, богато- etc.) für poetische
  Übersetzungen. Erkennt jetzt пышнокудрая, богаторогатого, темноносый.
- D5: Griechische Komposita-Präfixe erweitert — ἀμφι, πολύ, φίλο,
  πολύ etc. für Homer-Komposita (ἀμφοτέρωθεν, πολύτροπος etc.).
- D6: Griechische Komposita zeigen Originalformen (ἀμφοτέρωθεν statt
  αμφοτερωθεν) via norm_to_original-Mapping.

v59.7 CHANGES (B9–B14):
- B9: Greek content words — Funktionswörter (Präpositionen, Enklitika,
  Artikel, Partikel) werden vor top_content_words gefiltert. Zuvor erschienen
  επι, επει, κατα, εγω als „häufigste Inhaltswörter" — jetzt echte Lexik.
- B10: Greek top_content_words zeigt Originalformen MIT Diakritika
  (ἐπί statt επι, ἐγών statt εγων). Für Philologen lesbar.
- B11: Vergleichstabelle sortiert nach QuelLabel (Q1, Q2, Q3, Q4)
  statt nach Wortzahl. Konsistente Reihenfolge über Läufe hinweg.
- B12: Komposita-Abschnitt in format_stats_for_llm() — war bereits v59.6
  vorhanden, aber der Etappe1-Tab rendernte ihn nicht. Kein Code-Fix
  nötig, aber Validierung hinzugefügt.
- B13: Žukovskij (Q2) Stabilität — Vers-Split für russische Hexameter-
  Übersetzungen verbessert: Versnummern auf eigenen Zeilen werden jetzt
  auch im Standard-Pfad gefiltert (nicht nur im Greek-Pfad).
- B14: Russische Bindestrich-Komposita — _extract_composita() erkennt
  jetzt kyrillische Bindestrich-Komposita (бронзово-острое, темноносый,
  двузагнутых). Vorher: Nur DE-Bindestrich, RU fehlte komplett.

v59.5 CHANGES (B6+B7):
- B6: Greek sentence type detection (NS/gemischt statt 0/0)
- B7a: Greek paragraph stats verse-basiert (statt Absätze=1)
- B7b: Greek vowel echoes mit griech. Vokalsatz
- B7c: Greek sound patterns mit griech. Vokalen/Konsonanten
- Fazit-Verbesserung: reichhaltigere stats für Etappe 2+3

ÖFFENTLICHE API:
    from modules.text_analyzer import analyze_text, analyze_texts_comparative

    # Einzeltext-Analyse:
    stats = analyze_text("Mein langer Text...")

    # Vergleichende Analyse (für Etappe 2+3 Kontext):
    comparison = analyze_texts_comparative({"Quelle 1": "Text 1", "Quelle 2": "Text 2"})
"""

import re
import logging
import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ==============================================================================
# DEUTSCHE STOPPWÖRTER (Inhaltswörter vs. Funktionswörter)
# ==============================================================================
# Minimale Liste — reicht für Funktionswort-Identifikation.
# Kein Anspruch auf Vollständigkeit; erweiterbar via externe Wortliste (v57.5+).

_DE_FUNCTION_WORDS = frozenset({
    # Artikel
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines", "einem", "einen",
    # Pronomen
    "er", "sie", "es", "wir", "ihr", "ich", "du", "mich", "dich", "uns", "euch",
    "sein", "ihr", "mein", "dein", "sein", "unser", "euer",
    "dieser", "diese", "dieses", "jener", "jene", "jenes",
    "wer", "was", "welcher", "welche", "welches", "sich", "selbst",
    "mir", "dir", "ihm", "ihr", "ihnen", "uns", "euch",  # v59.1: Dativ-Pronomen
    # Praepositionen
    "in", "an", "auf", "aus", "bei", "mit", "nach", "von", "zu", "zur", "zum",
    "im", "am", "um", "ins", "ans", "aufs", "durchs", "fürs",  # v59.1: Präposition+Artikel-Verschmelzungen
    "über", "unter", "vor", "hinter", "neben", "zwischen", "durch", "für",
    "gegen", "ohne", "um", "bis", "seit", "während", "trotz", "wegen",
    # Konjunktionen
    "und", "oder", "aber", "doch", "jedoch", "denn", "weil", "da", "wenn", "falls",
    "obwohl", "obgleich", "während", "bevor", "nachdem", "seitdem", "sobald",
    "dass", "ob", "als", "wie", "so", "weder", "noch", "entweder",
    # Hilfsverben / Modalverben
    "ist", "sind", "war", "waren", "wird", "werden", "wurde", "wurden",
    "haben", "hat", "hatte", "hatten", "sein", "bin", "bist", "seid",
    "kann", "könnte", "muss", "müsste", "soll", "sollte", "will", "wolle",
    "darf", "dürfte", "lässt", "lassen",
    # Partikel / Adverbien (haeufige)
    "nicht", "auch", "noch", "schon", "wohl", "ja", "nein", "nun", "dann",
    "hier", "dort", "heute", "immer", "nie", "nur", "sehr", "ganz", "viel",
    "mehr", "wenig", "etwas", "alles", "nichts", "man", "mal", "halt",
    "ebenso", "zwar", "freilich", "allerdings", "natürlich", "vielleicht",
    # Relativpronomen
    "derjenige", "diejenige", "dasjenige",
})

# ==============================================================================
# RUSSISCHE STOPPWOERTER (Funktionswoerter)
# ==============================================================================
# Minimale Liste fuer Russisch — reicht fuer Funktionswort-Identifikation.

_RU_FUNCTION_WORDS = frozenset({
    # Praepositionen
    "в", "на", "с", "к", "у", "о", "от", "до", "по", "из", "за", "под",
    "над", "без", "для", "при", "через", "между", "перед", "после",
    # Pronomen
    "я", "ты", "он", "она", "оно", "мы", "вы", "они",
    "меня", "тебя", "его", "её", "нас", "вас", "их",
    "мне", "тебе", "ему", "ей", "нам", "вам", "им",
    "мной", "тобой", "ним", "ней", "нами", "вами", "ними",
    "мой", "твой", "наш", "ваш", "свой", "этот", "эта", "это", "эти",
    "тот", "та", "то", "те", "кто", "что", "который", "которая", "которое",
    "себя", "себе", "собой", "все", "всё", "весь", "вся", "каждый",
    # Konjunktionen / Partikel
    "и", "а", "но", "или", "да", "же", "ли", "не", "ни", "бы", "то",
    "если", "когда", "что", "чтобы", "потому", "поэтому", "так",
    "как", "чем", "то", "это", "уже", "ещё", "еще", "тоже", "также",
    # Hilfsverben / Modalverben
    "быть", "есть", "было", "будет", "были", "будут", "был", "была",
    "мочь", "могу", "может", "можем", "могут", "мог",
    "должен", "должна", "должны", "хотеть", "хочу", "хочет", "хотим",
    "иметь", "имеет", "имеем", "имеют",
    # Partikel / Adverbien
    "как", "так", "где", "там", "тут", "здесь", "сюда", "туда",
    "когда", "тогда", "теперь", "сейчас", "потом", "сначала",
    "очень", "тоже", "также", "уже", "ещё", "еще", "только",
    "даже", "ведь", "вот", "ну", "лишь", "почти", "просто",
})


# ==============================================================================
# SATZ-SEGMENTIERUNG
# ==============================================================================


# ── ALTGRIECHISCH-SUPPORT (Patch #7a) ──────────────────────────────
# Isolierter Pfad für polytonisches Griechisch. Wird nur aktiviert,
# wenn >50% der Zeichen im griechischen Unicode-Bereich liegen.

_GREEK_UNICODE_RANGES = re.compile(
    r'[\u0370-\u03FF\u1F00-\u1FFF]'  # Greek + Extended
)

def _is_greek_text(text: str, threshold: float = 0.3) -> bool:
    """Prüft ob Text überwiegend griechisch ist.
    NFD-sicher: Diakritika werden vor der Zählung entfernt."""
    if not text.strip():
        return False
    import unicodedata
    # NFD-Zerlegung + Diakritika-Entfernung für konsistente Zählung
    nfd = unicodedata.normalize('NFD', text)
    base_chars = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    greek_chars = len(_GREEK_UNICODE_RANGES.findall(base_chars))
    alpha_chars = len(re.findall(r'[a-zA-Z\u0370-\u03FF\u1F00-\u1FFF\u0400-\u04FF\u0590-\u05FF]', base_chars))
    return (greek_chars / max(alpha_chars, 1)) >= threshold

def _normalize_greek(word: str) -> str:
    """Entfernt polytonische Akzente für TTR-Berechnung.
    Behält Buchstaben und Grundform, entfernt Diakritika.

    C1-FIX (v59.8): Final-Sigma ς (U+03C2) wird zu Medial-Sigma σ (U+03C3)
    normalisiert. Grund: Die Funktionswortliste enthält τισ, ουτοσ, etc.
    mit Medial-Sigma, aber actual Greek text verwendet Final-Sigma am
    Wortende. Ohne diese Normalisierung matchen Funktionswörter wie
    τις (Indefinitpronomen) nicht gegen τισ in der Stopp-Liste.
    """
    import unicodedata
    # NFD zerlegt kombinierte Zeichen (Buchstabe + Akzent)
    nfd = unicodedata.normalize('NFD', word.lower())
    # Entferne alle kombinierenden Diakritika (Category Mn)
    stripped = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    # Re-kombiniere
    result = unicodedata.normalize('NFC', stripped)
    # C1-FIX: Final-Sigma → Medial-Sigma für konsistenten Vergleich
    result = result.replace('\u03C2', '\u03C3')  # ς → σ
    return result

# ── C2/C4: GRIECHISCHE ELISIONS- UND KRASIS-TABELLEN (v59.8) ──────
# Elision: Wenn ein Wort auf einen Vokal endet und das folgende Wort
# mit einem Vokal beginnt, fällt der Endvokal weg und wird durch
# Apostroph (᾽) ersetzt. z.B. ἔνθα → ἔνθ᾽, τότε → τότ᾽.
# Diese Tabelle rekonstruiert die Vollform aus der Elisionsform.
# Normalisiert (diakritika-frei, Final-Sigma → Medial-Sigma).

_GR_ELISION_RECONSTRUCTION = {
    # C2-FIX (v59.8): Elisionsformen (normalisiert) → (Vollform_mit_Diakritika, normalisiert)
    # Beide Formen gespeichert, damit norm_to_original korrekte Diakritika hat.
    "ενθ": ("ἔνθα", "ενθα"),      # ἔνθ᾽ → ἔνθα (dort)
    "τοτ": ("τότε", "τοτε"),      # τότ᾽ → τότε (dann)
    "ουκ": ("οὐκ", "ουκ"),       # οὐκ bleibt (schon voll)
    "μηκ": ("μὴκετι", "μηκετι"),    # μὴκ᾽ → μὴκετι (nicht mehr)
    "ουδ": ("οὐδέ", "ουδε"),      # οὐδ᾽ → οὐδέ (auch nicht)
    "μηδ": ("μὴδέ", "μηδε"),      # μὴδ᾽ → μὴδέ (auch nicht)
    "ουτ": ("οὐτέ", "ουτε"),      # οὐτ᾽ → οὐτέ (weder)
    "μητ": ("μὴτέ", "μητε"),      # μὴτ᾽ → μὴτέ (weder)
    "αλλ": ("ἀλλά", "αλλα"),      # ἀλλ᾽ → ἀλλά (aber)
    "επ": ("ἐπί", "επι"),        # ἐπ᾽ → ἐπί (auf)
    "απ": ("ἀπό", "απο"),        # ἀπ᾽ → ἀπό (von)
    "κατ": ("κατά", "κατα"),      # κατ᾽ → κατά (herab)
    "παρ": ("παρά", "παρα"),      # παρ᾽ → παρά (bei)
    "υπ": ("ὑπό", "υπο"),        # ὑπ᾽ → ὑπό (unter)
    "εφ": ("ἐπί", "επι"),        # ἐφ᾽ → ἐπί (auf, vor Vokal)
    "αφ": ("ἀπό", "απο"),        # ἀφ᾽ → ἀπό (von, vor Vokal)
    "δι": ("διά", "δια"),        # δι᾽ → διά (durch)
    "μετ": ("μετά", "μετα"),      # μετ᾽ → μετά (mit)
    "οιν": ("οἶνα", "οινα"),      # οἶν᾽ → οἶνα (das)
    "εισ": ("εἰσε", "εισε"),      # εἰσ᾽ → εἰσε (hinein)
    # C2b: Ein-Zeichen-Elisionsformen (Partikel)
    "δ": ("δέ", "δε"),        # δ᾽ → δέ (aber)
    "τ": ("τέ", "τε"),        # τ᾽ → τέ (und)
    "γ": ("γέ", "γε"),        # γ᾽ → γέ (enkl. Partikel)
    "κ": ("κι", "καν"),       # κ᾽ → κι=ἄν (wenn jemals)
    "ν": ("νύ", "νυ"),        # ν᾽ → νύ (nun)
    "ρ": ("ῤα", "ρα"),        # ῤ᾽ → ῤα (also, denn)
}

# C4: Krasis-Tabelle (zwei Wörter verschmelzen zu einem)
# Normalisiert: Krasis-Form → [Wort1, Wort2]
_GR_KRASIS_TABLE = {
    # C4-FIX (v59.8): Krasis-Form (normalisiert) → [(diacritical_1, norm_1), (diacritical_2, norm_2)]
    # WICHTIG: Die Schlüssel sind das Ergebnis von _normalize_greek() auf die Krasis-Form!
    "καγω":      [("καὶ", "και"), ("ἐγώ", "εγω")],        # κἀγώ → καὶ ἐγώ
    "καγων":     [("καὶ", "και"), ("ἐγών", "εγων")],      # κἀγών
    "χω":       [("καὶ", "και"), ("ὁ", "ο")],          # χὠ → καὶ ὁ
    "χη":       [("καὶ", "και"), ("ἡ", "η")],          # χὴ → καὶ ἡ
    "χοι":      [("καὶ", "και"), ("οἶ", "οι")],         # χοἶ → καὶ οἶ
    "κουκ":     [("καὶ", "και"), ("οὐκ", "ουκ")],        # κοὐκ → καὶ οὐκ
    "κουδε":    [("καὶ", "και"), ("οὐδέ", "ουδε")],       # κοὐδὲ → καὶ οὐδέ
    "κουχ":     [("καὶ", "και"), ("οὐυχ", "ουχ")],        # κοὐυχ → καὶ οὐυχ
    "κουτε":     [("καὶ", "και"), ("οὐτέ", "ουτε")],       # κοὐτ᾽ → καὶ οὐτέ
    "κωσ":      [("καὶ", "και"), ("ὡς", "ωσ")],         # κὠς → καὶ ὡς
    "κην":      [("καὶ", "και"), ("ἤν", "ην")],         # κἤν → καὶ ἤν
    "κει":      [("καὶ", "και"), ("εἶ", "ει")],         # κεἶ → καὶ εἶ
}


def _tokenize_greek(text: str) -> list[str]:
    """Tokenisierung für polytonisches Griechisch.

    C2-FIX (v59.8): Elisionsformen (ἔνθ᾽, τότ᾽, δ᾽, τ᾽) werden
    NICHT mehr in Trümmer gespalten. Stattdessen:
    (a) Rekonstruktion der Vollform über Elisions-Tabelle
    (b) bei unbekannter Elision: Token bleibt ungespalten
    Nie mehr: ἔνθ, τότ, κ als eigenständige „Wörter“.

    C4-FIX (v59.8): Krasis-Formen (κἀγώ, χὠ) werden erkannt und
    in ihre Bestandteile gesplittet.

    Apostroph-Varianten (\u2019, \u02bc, \u1fbd) werden standardisiert.
    Versnummern (87, 135) auf eigenen Zeilen werden gefiltert.
    """
    # Ersetze Apostroph-Varianten durch standardisierten korōnis
    normalized = text.replace('\u2019', '\u1fbd').replace('\u02bc', '\u1fbd')
    # Splitte an Whitespace
    raw_tokens = re.split(r"\s+", normalized)
    tokens = []
    for tok in raw_tokens:
        tok = tok.strip()
        if not tok:
            continue
        # Versnummern auf eigenen Zeilen filtern (z.B. "87", "135")
        if re.match(r'^\d+[a-z]?$', tok):
            continue
        # C4: Krasis-Erkennung — wenn Token normalisiert in Krasis-Tabelle
        tok_norm = _normalize_greek(tok)
        if tok_norm in _GR_KRASIS_TABLE:
            components = _GR_KRASIS_TABLE[tok_norm]
            # C4-FIX: Einträge sind jetzt [(diacritical, normalized), ...] Tuples
            diacritical_parts = []
            for comp in components:
                if isinstance(comp, tuple) and len(comp) == 2:
                    diacritical_parts.append(comp[0])  # Diakritika-Form
                else:
                    diacritical_parts.append(comp)  # Fallback
            tokens.extend(diacritical_parts)
            continue
        # C2: Elision behandeln — Token endet auf Apostroph (\u1fbd)
        # Prüfe ob es sich um eine bekannte Elision handelt
        elision_match = re.match(r'^([\u0370-\u03FF\u1F00-\u1FFF]+)([\u1FBD\u1FFE\u1FFD\'])$', tok)
        if elision_match:
            base = elision_match.group(1)
            base_norm = _normalize_greek(base)
            # Versuche Rekonstruktion über Elisions-Tabelle
            if base_norm in _GR_ELISION_RECONSTRUCTION:
                entry = _GR_ELISION_RECONSTRUCTION[base_norm]
                # C2-FIX: Einträge sind jetzt (diacritical, normalized) Tuples
                if isinstance(entry, tuple) and len(entry) == 2:
                    diacritical_form, normalized_form = entry
                    tokens.append(diacritical_form)  # Originalform mit Diakritika
                else:
                    tokens.append(entry)  # Fallback für alte Format
            else:
                # Unbekannte Elision: Token als Ganzes behalten (nicht spalten!)
                # Zuvor: base + apostrophe als zwei Trümmer → jetzt: ein Token
                tokens.append(base_norm if len(base_norm) > 1 else tok)
            continue
        # Normales Token (keine Elision, keine Krasis)
        # C2b-FIX: Zeichensetzung vom Token entfernen (Komma, Punkt etc.)
        tok_clean = re.sub(r"[,.;:!?·;᾽ι᾿῀῁῍῝῭]+", "", tok)
        if tok_clean and len(tok_clean) > 0:
            tokens.append(tok_clean)
    return tokens

def _split_sentences_greek(text: str) -> list[str]:
    """Satzsegmentierung für Altgriechisch.
    ; = Fragezeichen, · (ano teleia) = Satzende, . = selten."""
    # Ersetze griechische Interpunktion durch Standard-Trenner
    normalized = text.replace(';', '?').replace('·', '.')
    # Segmentiere an . ? ! (jetzt inkl. griechischer Äquivalente)
    sentences = re.split(r'(?<=[.?!])\s+', normalized)
    return [s.strip() for s in sentences if s.strip()]

def _count_syllables_greek(word: str) -> int:
    """Silbenzählung für Altgriechisch mit korrekter Diphthong-Behandlung.

    B5-FIX (v57.8): Drei Bugs behoben:
    1. Iota subscript (ᾳ/ῃ/ῳ) wird durch Normalisierung nicht mehr zerstört
    2. Diaeresis (ΐ/ϋ) bricht Diphthonge korrekt — Ἀτρεΐδης = 4 Silben
    3. NFC-Rekomposition nach selektivem Diakritika-Strip

    Algorithmus:
    1. Lowercase + NFD normalisieren
    2. Diaeresis auf ι/υ → Großbuchstabe 'I' (bricht Diphthong-Matching)
    3. Diakritika entfernen, ABER iota subscript (U+0345) behalten
    4. NFC rekomponieren → ᾳ/ῃ/ῳ bilden sich zurück für Diphthong-Matching
    5. Diphthonge durch Platzhalter 'V' ersetzen
    6. Verbleibende Vokale + Platzhalter zählen
    """
    import unicodedata as _ud

    if not word or not word.strip():
        return 0

    word_lower = word.lower()
    nfd = _ud.normalize('NFD', word_lower)

    # Step 1: Diaeresis (U+0308) auf ι/υ → bricht Diphthong
    # z.B. Ἀτρεΐδης: ΐ hat Diaeresis → ει ist KEIN Diphthong → 4 Silben
    chars = list(nfd)
    i = 0
    while i < len(chars):
        if chars[i] == '\u0308':  # combining diaeresis
            if i > 0 and chars[i - 1] in ('ι', 'υ'):
                chars[i - 1] = 'I'  # Großbuchstabe-Marker bricht Diphthong
                chars[i] = ''       # Diaeresis entfernen
        i += 1
    nfd_fixed = ''.join(chars)

    # Step 2: Diakritika entfernen, ABER iota subscript (U+0345) behalten
    # Iota subscript ist Category Mn, bildet aber Teil von Diphthongen (ᾳ, ῃ, ῳ)
    stripped = ''
    for c in nfd_fixed:
        cat = _ud.category(c)
        if cat == 'Mn' and c == '\u0345':  # combining Greek ypogegrammeni
            stripped += c
        elif cat != 'Mn':
            stripped += c

    # Step 3: NFC rekomponieren → alpha + iota_subscript → ᾳ etc.
    normalized = _ud.normalize('NFC', stripped)

    # Step 4: Diphthonge durch Platzhalter 'V' ersetzen
    diphthongs = [
        'αι', 'ει', 'οι', 'υι', 'αυ', 'ευ', 'ου', 'ηυ',
        'ᾳ', 'ῃ', 'ῳ',  # Iota-subscript-Diphthonge (jetzt erhalten!)
    ]
    count_word = normalized
    for d in diphthongs:
        count_word = count_word.replace(d, 'V')

    # Step 5: Verbleibende Vokale + Platzhalter zählen
    # 'I' = Diaeresis-gebrochener Vokal, 'V' = Diphthong-Platzhalter
    vowels = len(re.findall(r'[αεηιοωυIV]', count_word))
    return max(vowels, 1)


# ── B6: GRIECHISCHE SATZTYP-ERKENNUNG (v59.5) ────────────────────

# Griechische subordinierende Konjunktionen (NS-Einleiter)
# Normalisiert (diakritika-frei) für robustes Matching
_GR_NS_STARTERS_NORMALIZED = frozenset({
    # Subordinierende Konjunktionen
    "οτι", "ως", "ινα", "ει", "επει", "επειδη", "οτε", "οθεν",
    "μη", "πριν", "μεχρι", "οσπερ", "οστις", "οπη", "οπου",
    "οποτε", "οππως", "οπωσ", "οφρα", "τεως",
    # Relativpronomen (nach Normalisierung)
    "ος", "η", "ο", "οιου", "οποιος", "οσος", "οποσος",
    # Häufige enklitische Formen von Relativpronomen
    "ου", "ην", "αι", "ων", "οις", "ας", "ουσ",
    # Partikel die oft NS einleiten
    "ατε", "ειτε", "ητοι",
})

# Mehrwort-Konjunktionen (Pattern)
_GR_MULTI_WORD_NS = [
    r'ει\s+μη',          # εἰ μή (unless)
    r'ως\s+ου',          # ὡς οὐ (as not)
    r'οπως\s+ου',        # ὅπως οὐ (that not)
    r'οπως\s+αν',        # ὅπως ἄν (that ever)
    r'ως\s+αν',          # ὡς ἄν (whenever)
    r'οταν\s+αν',        # ὅταν ἄν (whenever)
]


def _classify_greek_sentence_type(sentence: str) -> str:
    """Klassifiziert einen griechischen Satz als HS, NS oder gemischt.

    B6-FIX (v59.5): Ersetzt hardcoded {"HS": total, "NS": 0, "gemischt": 0}.

    Heuristik:
    - NS: Beginnt mit subordinierender Konjunktion oder Relativpronomen
    - gemischt: Enthält NS-Marker irgendwo im Satz (Schachtelsatz)
    - HS: Keine NS-Marker gefunden

    Wörter werden vor dem Vergleich mit _normalize_greek() normalisiert
    (Diakritika entfernt), da die NS-Starter ebenfalls normalisiert sind.

    Args:
        sentence: Ein griechischer Satz (nach _split_sentences_greek()).

    Returns:
        "HS", "NS" oder "gemischt"
    """
    raw_words = sentence.split()
    if not raw_words:
        return "HS"

    # Erstes Wort normalisieren
    first_word = _normalize_greek(raw_words[0])
    if first_word in _GR_NS_STARTERS_NORMALIZED:
        return "NS"

    # Mehrwort-Konjunktionen im Gesamtsatz
    sent_lower = sentence.lower()
    for pattern in _GR_MULTI_WORD_NS:
        if re.search(pattern, sent_lower):
            return "gemischt"

    # NS-Marker irgendwo im Satz → gemischt (Schachtelsatz)
    for w in raw_words:
        clean = _normalize_greek(w)
        if clean in _GR_NS_STARTERS_NORMALIZED:
            return "gemischt"

    return "HS"


def _count_greek_sentence_types(sentences: list) -> dict:
    """Zählt HS, NS und gemischte Sätze für griechischen Text.

    B6-FIX (v59.5): Symmetrisch zu _count_sentence_types() im Standard-Pfad.
    """
    counts = {"HS": 0, "NS": 0, "gemischt": 0}
    for s in sentences:
        stype = _classify_greek_sentence_type(s)
        counts[stype] = counts.get(stype, 0) + 1
    return counts


# ── B7: GRIECHISCHE VOKAL- UND KLANGANALYSE (v59.5) ──────────────

# Griechische Vokale (inkl. mit Diakritika, nach NFD-Strip)
_GR_VOWELS = set('αεηιοωυ')

# Griechische Konsonanten für Alliteration
_GR_CONSONANTS = set('βγδζθκλμνξπρστφχψ')


def _extract_greek_vowel_skeleton(text: str) -> list:
    """Extrahiert Vokalgerüst für griechischen Text.

    B7b-FIX (v59.5): Ersetzt _extract_vowel_skeleton() für Griechisch,
    da die Standard-Version nur lateinische/kyrillische Vokale kennt.

    Arbeitet pro Vers (Zeile) und extrahiert die Vokalfolge jedes Worts.
    Verwendet _normalize_greek() für Diakritika-Entfernung vor Vokal-Matching.

    Returns:
        Liste von Dicts mit: line, skeleton, words.
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    result = []

    for line_idx, line in enumerate(lines):
        # Griechische Wörter extrahieren
        words = re.findall(r'[\u0370-\u03FF\u1F00-\u1FFF]+', line)
        if not words:
            continue

        word_skeletons = []
        for w in words:
            # Diakritika entfernen für Vokal-Matching
            norm = _normalize_greek(w)
            skel = ''.join(ch for ch in norm if ch in _GR_VOWELS)
            if skel:
                word_skeletons.append(skel)

        if word_skeletons:
            skeleton = '-'.join(word_skeletons)
            result.append({
                "line": line_idx + 1,
                "skeleton": skeleton,
                "words": words,
            })

    return result


def _detect_greek_vowel_echoes(text: str, verses: list = None) -> dict:
    """Erkennt Vokal-Echos in griechischem Verstext.

    B7b-FIX (v59.5): Ersetzt _detect_vowel_echoes() für Griechisch.
    Verwendet griechische Vokale (αεηιοωυ) statt lateinischer.

    Zwei-Pass-Verfahren:
    1. Trivialen Endvokal bestimmen (>50% der Versenden = trivial)
    2. Nicht-triviale Echos mit Abstand 1-5 finden

    Args:
        text: Der griechische Originaltext.
        verses: Optional: vorab erkannte Verse (sonst Zeilen-Split).

    Returns:
        Dict mit: echoes, trivial_vowel, trivial_ratio, rhyme_filtered, rhyme_filtered_count.
    """
    if verses:
        lines = verses
    else:
        lines = [l.strip() for l in text.split('\n') if l.strip()]

    if len(lines) < 2:
        return {"echoes": [], "trivial_vowel": None, "trivial_ratio": 0.0,
                "rhyme_filtered": False, "rhyme_filtered_count": 0}

    # Endvokal jedes Verses bestimmen
    line_end_vowels = []
    for idx, line in enumerate(lines):
        words = re.findall(r'[\u0370-\u03FF\u1F00-\u1FFF]+', line)
        end_vowel = None
        if words:
            last_word = _normalize_greek(words[-1])
            for ch in reversed(last_word):
                if ch in _GR_VOWELS:
                    end_vowel = ch
                    break
        line_end_vowels.append({"line": idx + 1, "end_vowel": end_vowel})

    # Trivialen Endvokal bestimmen
    vowel_counts = Counter(lev["end_vowel"] for lev in line_end_vowels if lev["end_vowel"])
    total_with_vowel = sum(vowel_counts.values())
    trivial_vowel = None
    trivial_ratio = 0.0
    if total_with_vowel > 0:
        most_common_vowel, most_common_count = vowel_counts.most_common(1)[0]
        trivial_ratio = most_common_count / total_with_vowel
        if trivial_ratio > 0.5:
            trivial_vowel = most_common_vowel

    # Echos finden
    echoes = []
    for i in range(len(line_end_vowels)):
        if not line_end_vowels[i]["end_vowel"]:
            continue
        for j in range(i + 1, min(i + 6, len(line_end_vowels))):
            if not line_end_vowels[j]["end_vowel"]:
                continue
            if line_end_vowels[i]["end_vowel"] == line_end_vowels[j]["end_vowel"]:
                # Triviale Echos überspringen
                if trivial_vowel and line_end_vowels[i]["end_vowel"] == trivial_vowel:
                    continue
                distance = j - i
                echoes.append({
                    "line_a": line_end_vowels[i]["line"],
                    "line_b": line_end_vowels[j]["line"],
                    "end_vowel": line_end_vowels[i]["end_vowel"],
                    "distance": distance,
                })

    echoes.sort(key=lambda e: e["distance"])
    # v59.9.2 Fix 2026-06-21: echoes[:12] war ein Cap, das alle Quellen
    # auf „12 Vokal-Echos" begrenzte — Artefakt, das die Synthese zu
    # falschen Schlüssen verleitete. Jetzt: Cap 50 für Speicher,
    # zusätzlich echoes_count für echte numerische Vergleiche.
    return {
        "echoes": echoes[:50],
        "echoes_count": len(echoes),  # v59.9.2: echte Anzahl
        "trivial_vowel": trivial_vowel,
        "trivial_ratio": round(trivial_ratio, 2),
        "rhyme_filtered": False,  # Altgriech. Epik hat keinen Endreim
        "rhyme_filtered_count": 0,
    }


def _detect_greek_sound_patterns(text: str, verses: list = None) -> dict:
    """Erkennt Klangfiguren in griechischem Text: Alliteration, Assonanz.

    B7c-FIX (v59.5): Ersetzt _detect_sound_patterns() für Griechisch.
    Verwendet griechische Vokale und Konsonanten statt lateinischer.

    Altgriechische Epik verwendet:
    - Alliteration: Gleicher Anlautkonsonant in Inhaltswörtern
      (besonders häufig bei Homer: μ-Alliteration, π-Alliteration)
    - Assonanz: Gleiche Vokalfolge in Wörtern
    - KEIN Binnenreim (Altgriech. Epik reimt nicht)

    Args:
        text: Der griechische Originaltext.
        verses: Optional: vorab erkannte Verse.

    Returns:
        Dict mit: alliterations, assonances, internal_rhymes (immer leer für Griechisch).
    """
    # Griechische Funktionswörter (häufigste, für Filterung)
    _GR_FUNCTION_WORDS = frozenset({
        "ο", "η", "το", "του", "τησ", "την", "τοισ", "τασ",
        "και", "δε", "τε", "μεν", "αρ", "ρα", "αν", "ουκ",
        "ου", "μη", "ει", "ως", "εν", "επ", "παρ", "κατ",
        "περ", "απο", "δια", "υπερ", "προσ", "παρα", "ανα",
        "αλλ", "αλλα", "γαρ", "ουν", "μεν", "δη", "τοι",
        "ουδε", "μηδε", "ουτε", "μητε", "η", "ητοι", "ειτε",
    })

    if verses:
        lines = verses
    else:
        lines = [l.strip() for l in text.split('\n') if l.strip()]

    alliterations = []
    assonances = []
    line_content_initials = []

    def _gr_first_consonant(word):
        """Erster Konsonant eines griechischen Worts (normalisiert)."""
        norm = _normalize_greek(word)
        for ch in norm:
            if ch in _GR_CONSONANTS:
                return ch
        return None

    def _gr_vowel_pattern(word):
        """Vokalfolge eines griechischen Worts (normalisiert)."""
        norm = _normalize_greek(word)
        return ''.join(ch for ch in norm if ch in _GR_VOWELS)

    for line_idx, line in enumerate(lines):
        words_all = re.findall(r'[\u0370-\u03FF\u1F00-\u1FFF]+', line)
        if len(words_all) < 2:
            line_content_initials.append({})
            continue

        # Funktionswörter filtern
        content_words = [w for w in words_all
                         if _normalize_greek(w) not in _GR_FUNCTION_WORDS
                         and len(w) > 2]

        # Alliteration: Gleicher Anlautkonsonant in Inhaltswörtern
        initials = {}
        for w in content_words:
            fc = _gr_first_consonant(w)
            if fc:
                if fc not in initials:
                    initials[fc] = []
                norm_w = _normalize_greek(w)
                if norm_w not in [_normalize_greek(x) for x in initials[fc]]:
                    initials[fc].append(w)

        line_content_initials.append(initials)

        for consonant, wlist in initials.items():
            if len(wlist) >= 2:
                alliterations.append({
                    "line": line_idx + 1,
                    "consonant": consonant,
                    "words": wlist[:5],
                    "text": line[:80],
                })

        # Assonanz: Gleiche Vokalfolge in Inhaltswörtern
        word_vowels = [(w, _gr_vowel_pattern(w)) for w in content_words if len(w) > 3]
        for i in range(len(word_vowels)):
            for j in range(i + 1, min(i + 4, len(word_vowels))):
                w1, v1 = word_vowels[i]
                w2, v2 = word_vowels[j]
                if len(v1) >= 2 and len(v2) >= 2 and v1[:2] == v2[:2]:
                    nw1, nw2 = _normalize_greek(w1), _normalize_greek(w2)
                    if nw1 != nw2:
                        assonances.append({
                            "line": line_idx + 1,
                            "vowel_pattern": v1[:2],
                            "word_a": w1,
                            "word_b": w2,
                        })

    # Versübergreifende Alliteration (Abstand 1-2 Verse)
    for dist in (1, 2):
        for i in range(len(lines) - dist):
            j = i + dist
            initials_i = line_content_initials[i] if i < len(line_content_initials) else {}
            initials_j = line_content_initials[j] if j < len(line_content_initials) else {}
            shared = set(initials_i.keys()) & set(initials_j.keys())
            for consonant in shared:
                words_i = initials_i[consonant]
                words_j = initials_j[consonant]
                cross_words = [w for w in words_j
                               if _normalize_greek(w) not in [_normalize_greek(x) for x in words_i]]
                if not cross_words:
                    continue
                combined = words_i + cross_words
                already_found = any(
                    existing.get("consonant") == consonant
                    and existing.get("line") in (i + 1, j + 1)
                    for existing in alliterations
                )
                if not already_found:
                    alliterations.append({
                        "line": i + 1,
                        "line_end": j + 1,
                        "consonant": consonant,
                        "words": combined[:5],
                        "text": f"{lines[i][:40]} | {lines[j][:40]}",
                        "cross_verse": True,
                    })

    # v59.9.1 Fix 2026-06-21: Listen nicht truncaten (war [:20]/[:15]).
    # Vorher: truncation führte zu „alle Quellen haben 20 Alliterationen" —
    # ein Artefakt, das die Synthese zu falschen Schlüssen verleitete.
    # Jetzt: volle Listen behalten (für Belege), zusätzlich count-Felder
    # für echte numerische Vergleiche in der Synthese.
    # Cap bei 50 zum Speicherschutz (Extremfälle, sehr lange Texte).
    return {
        "alliterations": alliterations[:50],  # Cap für Speicher, nicht für Statistik
        "assonances": assonances[:50],
        "internal_rhymes": [],  # Altgriech. Epik: kein Binnenreim
        "alliterations_count": len(alliterations),  # v59.9.1: echte Anzahl
        "assonances_count": len(assonances),
        "internal_rhymes_count": 0,
    }


# ── B4: GRIECHISCHE VERS- UND STROPHENERKENNUNG (v57.8) ───────────

def _detect_greek_verses(text: str) -> list:
    """Spaltet griechischen Text in Verse, filtert Versnummern und Leerzeilen.

    Altgriechischer Epik (Homer) ist zeilengetrennt. Editionen mischen
    oft Versnummern (z.B. "87" auf eigenen Zeilen) ein — diese werden gefiltert.

    Args:
        text: Der griechische Text.

    Returns:
        Liste von Vers-Strings (nicht-leer, keine Versnummern).
    """
    lines = text.split('\n')
    verses = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Eigenständige Versnummern filtern (z.B. "87", "88", "123a")
        if re.match(r'^\d+[a-z]?$', stripped):
            continue
        verses.append(stripped)
    return verses


def _detect_greek_stanzas(text: str) -> dict:
    """Erkennt Strophenstruktur in griechischem Verstext.

    Strophen werden durch Leerzeilen im Originaltext getrennt.
    Versnummern werden vor dem Zählen der Zeilen pro Strophe gefiltert.
    Verwendet dieselbe Dict-Struktur wie _detect_stanzas() für Kompatibilität.

    D2-FIX (v59.9): Kontinuierlicher Hexameter (keine Leerzeilen) wird jetzt
    wie die russischen Übersetzungen behandelt — jeder Vers = 1 Strophe.
    Vorher: Alle 94 Zeilen in 1 Strophe → „Strophen: 1 (94)".
    Jetzt: 94 Einzelvers-Strophen → „Strophen: 94 (1-1-1-...)" — konsistent
    mit Q1-Q3 und korrekt für Homerdichtung ohne Strophengliederung.
    """
    raw_stanzas = text.split('\n\n')
    stanzas = []
    for block in raw_stanzas:
        lines = []
        for line in block.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r'^\d+[a-z]?$', stripped):
                continue
            lines.append(stripped)
        if lines:
            stanzas.append(lines)

    # D2-FIX: Wenn nur eine einzige Strophe mit >5 Zeilen erkannt wurde
    # (kontinuierlicher Hexameter ohne Leerzeilen-Trennung), dann
    # jede Zeile als eigene Strophe behandeln — konsistent mit den
    # russischen Übersetzungen, die auch 1-1-1-... zeigen.
    if len(stanzas) == 1 and len(stanzas[0]) > 5:
        stanzas = [[line] for line in stanzas[0]]

    if not stanzas:
        return {"stanza_count": 0, "lines_per_stanza": [], "stanzas": [], "stanza_pattern": ""}

    lines_per_stanza = [len(s) for s in stanzas]
    stanza_pattern = "-".join(str(n) for n in lines_per_stanza)

    return {
        "stanza_count": len(stanzas),
        "lines_per_stanza": lines_per_stanza,
        "stanzas": ["\n".join(s) for s in stanzas],
        "stanza_pattern": stanza_pattern,
    }


def _detect_greek_enjambement(verses: list) -> dict:
    """Erkennt Enjambements in griechischem Vers.

    Enjambement = Versgrenze, die NICHT mit Satzgrenze zusammenfällt.
    Im Altgriechischen sind satzabschließende Zeichen:
      - Ano Teleia (·) = Haupteinschnitt / Satzgrenze
      - Griechisches Fragezeichen (;) = Satzgrenze
      - Punkt (.) = Satzgrenze
    Komma (,) am Versende blockiert Enjambement NICHT — typisch für Homer.
    """
    if len(verses) < 2:
        return {"enjambements": [], "count": 0, "percentage": 0.0}

    sentence_final = set('·;.')
    enjambements = []

    for i in range(len(verses) - 1):
        current = verses[i].rstrip()
        next_v = verses[i + 1].strip()
        if not current or not next_v:
            continue

        last_char = current[-1] if current else ''
        if last_char not in sentence_final:
            enjambements.append({
                "from_line": i + 1,
                "to_line": i + 2,
                "fragment_a": current[-60:] if len(current) > 60 else current,
                "fragment_b": next_v[:60] if len(next_v) > 60 else next_v,
            })

    total_transitions = len(verses) - 1
    percentage = round(len(enjambements) / total_transitions * 100, 1) if total_transitions > 0 else 0.0

    return {
        "enjambements": enjambements,
        "count": len(enjambements),
        "percentage": percentage,
    }


def _analyze_greek_rhythm(verses: list) -> dict:
    """Analysiert Versrhythmus für griechischen Text: Silben pro Vers, Regelmäßigkeit.

    Verwendet _count_syllables_greek() für präzise griechische Silbenzählung.
    Liefert dieselbe Dict-Struktur wie _analyze_verse_rhythm() für Kompatibilität.

    Args:
        verses: Liste von Vers-Strings (bereits gefiltert).

    Returns:
        Dict mit: syllables_per_line, avg_syllables, stdev_syllables,
        is_regular, pattern_description
    """
    if not verses:
        return {
            "syllables_per_line": [],
            "avg_syllables": 0.0,
            "stdev_syllables": 0.0,
            "is_regular": False,
            "pattern_description": "",
        }

    # Einfacher griechischer Tokenizer (nur griechische Wort-Token)
    def _simple_greek_tokenize(text):
        return [w for w in re.findall(r'[\u0370-\u03FF\u1F00-\u1FFF]+', text) if len(w) > 1]

    syllables_per_line = []
    for verse in verses:
        words = _simple_greek_tokenize(verse)
        total = sum(_count_syllables_greek(w) for w in words if len(w) > 1)
        syllables_per_line.append(total)

    if not syllables_per_line:
        return {
            "syllables_per_line": [],
            "avg_syllables": 0.0,
            "stdev_syllables": 0.0,
            "is_regular": False,
            "pattern_description": "",
        }

    avg = sum(syllables_per_line) / len(syllables_per_line)
    variance = sum((s - avg) ** 2 for s in syllables_per_line) / len(syllables_per_line) if len(syllables_per_line) > 1 else 0
    stdev = math.sqrt(variance)

    # Hexameter: typisch 12-17 Silben, σ < 2.0 → regelmäßig
    is_regular = stdev < 2.0

    if is_regular:
        rounded_avg = round(avg)
        if 12 <= rounded_avg <= 17:
            pattern_description = f"Hexameter ({rounded_avg} Silben)"
        elif 6 <= rounded_avg <= 9:
            pattern_description = f"regelmäßiger Vers ({rounded_avg} Silben)"
        else:
            pattern_description = f"regelmäßiger Rhythmus ({rounded_avg} Silben)"
    else:
        pattern_description = f"freier Rhythmus (σ {stdev:.1f})"

    return {
        "syllables_per_line": syllables_per_line,
        "avg_syllables": round(avg, 1),
        "stdev_syllables": round(stdev, 1),
        "is_regular": is_regular,
        "pattern_description": pattern_description,
    }


def _analyze_greek_verse_detail(text: str, verses: list, sentences: list) -> dict:
    """Baut vollständiges verse_detail-Dict für altgriechischen Text.

    B4-FIX (v57.8): Ersetzt _get_empty_verse_detail() durch echte Analyse.
    Produziert dieselbe Dict-Struktur wie der Standardpfad, aber mit
    griechischen Anpassungen:

    - Strophen: über Leerzeilen erkannt, Versnummern gefiltert
    - Reim: Altgriech. Epik verwendet keinen Endreim → immer "Kein Reim"
    - Enjambement: Griechische Heuristik (· und ; sind satzfinal)
    - Rhythmus: _count_syllables_greek() für präzise Silbenzählung

    Args:
        text: Der Originaltext.
        verses: Liste von Vers-Strings aus _detect_greek_verses().
        sentences: Liste von Satz-Strings.

    Returns:
        Vollständiges verse_detail-Dict.
    """
    # Strophen (leerzeilengetrennt)
    stanzas = _detect_greek_stanzas(text)

    # Reim — Altgriech. Epik verwendet keinen Endreim
    rhyme = {
        "rhyme_pairs": [],
        "scheme_labels": [],
        "scheme_notation": "",
        "rhyme_type": "Kein Reim",
    }

    # Klangfiguren — B7c-FIX: griechenspezifische Klanganalyse
    sound_patterns = _detect_greek_sound_patterns(text, verses)

    # Enjambement — griechische Heuristik
    enjambement = _detect_greek_enjambement(verses)

    # Rhythmus — griechische Silbenzählung
    rhythm = _analyze_greek_rhythm(verses)

    # Vokalgerüste — B7b-FIX: griechenspezifische Vokal-Extraktion
    vowel_skeletons = _extract_greek_vowel_skeleton(text)

    # Vokal-Echos — B7b-FIX: griechenspezifische Echo-Erkennung
    vowel_echoes = _detect_greek_vowel_echoes(text, verses)

    return {
        "stanzas": stanzas,
        "rhyme": rhyme,
        "sound_patterns": sound_patterns,
        "enjambement": enjambement,
        "rhythm": rhythm,
        "vowel_skeletons": vowel_skeletons,
        "vowel_echoes": vowel_echoes,
    }


def _get_empty_verse_detail() -> Dict:
    """Liefert die Standard-Struktur für verse_detail mit Null-Werten.
    
    v59.3-fix (Kimi Audit B1): Stellt sicher, dass alle Sprachpfade dieselbe
    verse_detail-Struktur liefern — auch wenn Lyrik nicht erkannt wird.
    Verhindert PyArrow-Typfehler bei gemischten Quellen (int vs str "—").
    """
    return {
        "stanzas": {
            "stanza_count": 0,
            "lines_per_stanza": [],
            "stanzas": [],
            "stanza_pattern": "",
        },
        "rhyme": {
            "rhyme_pairs": [],
            "scheme_labels": [],
            "scheme_notation": "",
            "rhyme_type": "Kein Reim",
        },
        "sound_patterns": {
            "alliterations": [],
            "assonances": [],
            "internal_rhymes": [],
        },
        "enjambement": {
            "enjambements": [],
            "count": 0,
            "percentage": 0.0,
        },
        "rhythm": {
            "syllables_per_line": [],
            "avg_syllables": 0.0,
            "stdev_syllables": 0.0,
            "is_regular": False,
            "pattern_description": "",
        },
        "vowel_skeletons": [],
        "vowel_echoes": {
            "echoes": [],
            "trivial_vowel": None,
            "trivial_ratio": 0.0,
            "rhyme_filtered": False,
            "rhyme_filtered_count": 0,
        },
    }


def _analyze_greek(text: str, source_label: str = "Quelle") -> dict:
    """Vollständige Etappe-1-Analyse für altgriechische Texte.

    B4/B5-FIX (v57.8): Verse detection, echte Silbenzählung, Enjambement,
    Strophenstruktur und korrigierte morphologische Komplexität.
    B6-FIX (v59.5): Echte Satztyperkennung (NS/gemischt statt 0/0).
    B7-FIX (v59.5): Verse-basierte Absatzstatistik, griech. Vokal-/Klanganalyse.
    """
    sentences = _split_sentences_greek(text)
    words_raw = _tokenize_greek(text)
    words_normalized = [_normalize_greek(w) for w in words_raw if len(w) > 1]
    
    total_words = len(words_normalized)
    total_sentences = len(sentences)
    
    # B2-Fix: Echte Satzstatistiken statt avg für alle 4 Werte (Kimi B2)
    sentence_lengths = [len(_tokenize_greek(s)) for s in sentences]
    sentence_lengths_sorted = sorted(sentence_lengths) if sentence_lengths else [0]
    avg_sentence_length = round(sum(sentence_lengths) / max(len(sentence_lengths), 1), 1)
    median_sentence_length = round(sentence_lengths_sorted[len(sentence_lengths_sorted) // 2], 1)
    max_sentence_length = max(sentence_lengths) if sentence_lengths else 0
    min_sentence_length = min(sentence_lengths) if sentence_lengths else 0
    
    # B6-Fix: Echte Satztyperkennung statt hardcoded NS=0, gemischt=0
    sentence_types = _count_greek_sentence_types(sentences)
    
    # TTR mit normalisierten Tokens
    unique_words = set(words_normalized)
    ttr = round(len(unique_words) / max(total_words, 1), 3)
    
    # B5-Fix: Morphologische Komplexität mit Standard-Formel
    # (avg Wortlänge + langer-Wort-Anteil × 3) statt (Anteil >8 × 10)
    avg_word_length = sum(len(w) for w in words_normalized) / max(total_words, 1)
    long_word_ratio = sum(1 for w in words_normalized if len(w) > 10) / max(total_words, 1)
    morph_complexity = round(avg_word_length + (long_word_ratio * 3), 2)
    
    # Silbenstatistik
    syllable_counts = [_count_syllables_greek(w) for w in words_raw if len(w) > 1]
    avg_syllables = round(sum(syllable_counts) / max(len(syllable_counts), 1), 1)
    
    # Interpunktion
    comma_count = text.count(',')
    period_count = text.count('.') + text.count('·')
    question_count = text.count(';')
    
    # B4-Fix: Griechische Versgrenzen-Erkennung
    verses = _detect_greek_verses(text)
    words_per_verse = [len(_tokenize_greek(v)) for v in verses]
    avg_words_per_verse = sum(words_per_verse) / max(len(words_per_verse), 1)
    
    # Lyrik-Signal (griechisch-spezifische Schwellenwerte)
    # Hexameter: typisch 5-8 Wörter/Vers
    if avg_words_per_verse < 10 and len(verses) > 5:
        lyrik_signal = "stark"
    elif avg_words_per_verse < 14 and len(verses) > 3:
        lyrik_signal = "mittel"
    else:
        lyrik_signal = "schwach"
    
    # Vers-Standardabweichung
    if len(words_per_verse) > 1:
        verse_var = sum((w - avg_words_per_verse) ** 2 for w in words_per_verse) / len(words_per_verse)
        stdev_words_per_verse = round(math.sqrt(verse_var), 1)
    else:
        stdev_words_per_verse = 0
    
    # B4/B5-Fix: Vollständiges verse_detail mit griechenspezifischer Analyse
    if len(verses) >= 2 and lyrik_signal in ("stark", "mittel"):
        verse_detail = _analyze_greek_verse_detail(text, verses, sentences)
    else:
        verse_detail = _get_empty_verse_detail()
    
    # B7a-Fix: Absatzstatistik — VERSE-BASIERT für Verstexte
    # Vorher: Strophen-basiert → bei zusammenhängendem Hexameter "1 Absatz (Ø 4268)"
    # Jetzt: Vers-basiert → "94 Absätze (Ø 45.3, σ 12.1)" — viel aussagekräftiger
    if len(verses) > 3:
        verse_lens = [len(v) for v in verses]
        avg_verse_len = sum(verse_lens) / len(verse_lens)
        verse_var = sum((l - avg_verse_len) ** 2 for l in verse_lens) / len(verse_lens)
        paragraph_stats = {
            "count": len(verses),
            "avg_chars": round(avg_verse_len, 1),
            "min_chars": min(verse_lens),
            "max_chars": max(verse_lens),
            "length_variance": round(math.sqrt(verse_var), 1) if len(verse_lens) > 1 else 0,
        }
    else:
        # Fallback für nicht-versartige griechische Texte
        greek_stanzas = _detect_greek_stanzas(text)
        if greek_stanzas["stanza_count"] > 0 and greek_stanzas["stanzas"]:
            stanza_lens = [len(s) for s in greek_stanzas["stanzas"]]
            paragraph_stats = {
                "count": greek_stanzas["stanza_count"],
                "avg_chars": round(sum(stanza_lens) / len(stanza_lens), 1),
                "min_chars": min(stanza_lens),
                "max_chars": max(stanza_lens),
                "length_variance": round(math.sqrt(
                    sum((l - sum(stanza_lens)/len(stanza_lens))**2 for l in stanza_lens) / len(stanza_lens)
                ), 1) if len(stanza_lens) > 1 else 0,
            }
        else:
            paragraph_stats = {
                "count": 1,
                "avg_chars": len(text),
                "min_chars": len(text),
                "max_chars": len(text),
                "length_variance": 0,
            }
    
    # Hotspot-Sätze für griechisch (B7: reicht top-3 für Etappe 2+3)
    hotspot_sentences = []
    if sentences:
        # Einfache Hotspot-Heuristik: längste Sätze + Sätze mit Kontrastpartikeln
        scored = []
        for s in sentences:
            score = 0.0
            words_s = _tokenize_greek(s)
            score += len(words_s) / max(avg_sentence_length, 1) * 0.3
            # Griechische Kontrastpartikel
            for w in words_s:
                nw = _normalize_greek(w)
                if nw in ("αλλα", "αλλ", "μεν", "δε", "τε", "γαρ", "ουν"):
                    score += 0.2
                    break
            scored.append({"sentence": s, "score": round(score, 2), "reasons": ["griech. Hotspot"]})
        scored.sort(key=lambda x: x["score"], reverse=True)
        hotspot_sentences = scored[:3]

    # v59.6: Komposita / Wortschöpfungen für Griechisch
    # D6-FIX (v59.9): Originalformen (mit Diakritika) in Komposita-Anzeige.
    # Vorher: words_normalized (diakritika-frei) → „αμφοτερωθεν".
    # Jetzt: norm_to_original-Mapping für philologisch lesbare Formen
    # → „ἀμφοτέρωθεν". Matching weiterhin über normalisierte Formen.
    # HINWEIS: _extract_composita() wird HIER nur deklariert (vor norm_to_original),
    # die Originalform-Zuordnung erfolgt NACH norm_to_original-Erstellung weiter unten.
    greek_composita = _extract_composita(words_normalized, sentences, max_items=10, language="el")

    # B9-FIX (v59.7): Griechische Funktionswörter VOLLSTÄNDIG filtern.
    # Vorher: Nur eine Teilmenge → επι, επει, κατα, εγω erschienen als
    # „häufigste Inhaltswörter". Jetzt: Erweiterte Liste mit Präpositionen,
    # Enklitika, Artikelformen, Pronomina, Partikeln.
    # B10-FIX: Originalformen (mit Diakritika) in top_content_words zeigen.
    content_word_freq = Counter()
    function_word_freq = Counter()
    _GR_FUNC_NORMALIZED = frozenset({
        # Bestimmter Artikel (normalisiert)
        "ο", "η", "το", "του", "τησ", "την", "τοισ", "τασ",
        "τοι", "ται", "τασ", "των", "τηι", "τοισ",
        "τω", "τη", "ται", "τοι", "τοισ", "την", "τασ",
        # Unbestimmter Artikel / Pronomen
        "τισ", "τι", "τινα", "τινεσ", "τινοσ",
        # Präpositionen (akzent-normalisiert) — B9: VOLLSTÄNDIG
        "εν", "επι", "επει", "επειδη", "κατα", "παρα",
        "περι", "απο", "δια", "υπο", "υπερ", "προ",
        "προσ", "ανα", "εκ", "εξ", "μετα", "συν",
        "αντι", "εωσ", "αχρι", "μεχρι", "χωρισ",
        "εω", "παρ", "κατ", "αμφι",
        # Konjunktionen / Partikel
        "και", "δε", "τε", "μεν", "αρ", "ρα", "αν",
        "ουκ", "ου", "ουχ", "μη", "ει", "ωσ",
        "αλλ", "αλλα", "γαρ", "ουν", "δη", "τοι",
        "ουδε", "μηδε", "ουτε", "μητε", "ητοι", "ειτε",
        "επειτα", "νυν", "αταρ", "αυταρ", "αρα",
        # D1-FIX (v59.9): Kopula (εἰμί) — Vorher fehlten alle Formen von
        # „sein" → ἦεν (3x als Inhaltswort!), ἦν, ἔστι etc.
        "ηεν",     # ἦεν (epic imperfect, 3sg — war als Inhaltswort!)
        "ην",      # ἦν (imperfect 3sg)
        "εστι",    # ἔστι (present 3sg)
        "εστιν",   # ἔστιν (present 3sg, enclitic form)
        "ειμι",    # εἰμί (present 1sg)
        "εισι",    # εἰσί (present 3pl)
        "εισιν",   # εἰσίν (present 3pl, enclitic)
        "ησαν",    # ἦσαν (imperfect 3pl)
        "εσται",   # ἔσται (future 3sg)
        "εσονται", # ἔσονται (future 3pl)
        "εσμεν",   # ἐσμέν (present 1pl)
        "εστω",    # ἔστω (imperative)
        "ειη",     # εἴη (optative 3sg)
        "ειησαν",  # εἴησαν (optative 3pl)
        "εστε",    # ἐστέ (present 2pl)
        "εμεν",    # ἔμεν (epic imperfect)
        "εμεναι",  # ἔμεναι (infinitive)
        # D1-FIX: Quantorpronomina — πάντεσ erschien als Inhaltswort
        "παντεσ",  # πάντεσ (all, nom. masc.)
        "παντα",   # πάντα (all, acc. neut.)
        "πασι",    # πᾶσι (all, dat. masc./neut.)
        "πασιν",   # πᾶσιν (all, dat. masc./neut.)
        "πασαν",   # πᾶσαν (all, acc. fem.)
        "πασησ",   # πάσησ (all, gen. fem.)
        "πασαι",   # πᾶσαι (all, nom. fem.)
        "παντοσ",  # πάντοσ (all, gen. masc./neut.)
        "παντι",   # παντί (all, dat. masc./neut.)
        # D1-FIX: Enklitische Partikel ἄρ/ἀρά — νόημα als Bigramm-Partner
        # Vorher: ἄρ normalisiert zu αρ, nicht in Liste → „μὲν αρ" Bigramm
        "αρ",      # ἄρ (enclitic particle, already listed above but explicit)
        "αρα",     # ἄρα (postpositive particle)
        # D1-FIX: Weitere häufige Homerpromina
        "αυτοσ",   # αὐτόσ (self/same)
        "αυτη",    # αὐτή (self/same, fem.)
        "αυτο",    # αὐτό (self/same, neut.)
        "αυτου",   # αὐτοῦ (his/its)
        "αυτησ",   # αὐτῆσ (her)
        "αυτοισ",  # αὐτοῖσ (them, dat.)
        "αυτασ",   # αὐτάσ (them, acc. fem.)
        "αυτουσ",  # αὐτούσ (them, acc. masc.)
        "αυταισ",  # αὐταῖσ (them, dat. fem.)
        "εκεινο",  # ἐκεῖνο (that)
        "εκεινοσ", # ἐκεῖνοσ (that, masc.)
        "εκεινη",  # ἐκεινή (that, fem.)
        # Personalpronomina (normalisiert) — B9: εγω, εγων raus
        "εγω", "εγων", "με", "μου", "μοι", "εμε",
        "συ", "σε", "σου", "σοι", "σφε",
        "ημεισ", "υμεισ", "σφω", "σφισι",
        # Demonstrativ-/Relativpronomina
        "ουτοσ", "ουτωσ", "τουτο", "εκεινοσ",
        "οστισ", "ητισ", "οστισ", "οπποιοσ", "οπποσον",
        # Zahlwörter (häufige)
        "εισ", "δυο", "τρεισ", "τεσσαρεσ",
        # Adverbien
        "ουτω", "ωδε", "μαλα", "πολλα",
        # C2-FIX (v59.8): Rekonstruierte Elisionsformen als Funktionswörter
        # ἔνθ᾽ → ἔνθα (dort), τότ᾽ → τότε (dann) etc.
        "ενθα", "τοτε", "μηκετι", "εισε",
        # Enklitika / Krasis
        "γε", "περ", "τοι",
        # D1-FIX: Weitere häufige Partikel/Adverbien aus Homer
        "ναι",     # ναί (yes)
        "ουχι",    # οὐχί (not indeed)
        "ουκουν",  # οὐκοῦν (therefore not)
        "επειτα",  # ἔπειτα (thereafter)
        "ηδη",     # ἤδη (already)
        "οττε",    # ὅττε (whenever, epic)
        "οπποτε",  # ὁππότε (whenever)
        "οππωσ",   # ὅππωσ (how that)
        "τεθ",     # epic particle form
    })
    # B10: Mapping normalisiert → Originalform (fuer Anzeige mit Diakritika)
    # Wir speichern die erste Originalform, die wir fuer jedes normalisierte Wort sehen.
    norm_to_original = {}
    for raw_w in words_raw:
        if len(raw_w) <= 1:
            continue
        norm_w = _normalize_greek(raw_w)
        if norm_w not in norm_to_original:
            norm_to_original[norm_w] = raw_w

    # D6-FIX (v59.9): Komposita-Originalformen nachträglich zuordnen.
    # _extract_composita() wurde oben mit words_normalized aufgerufen,
    # daher enthalten die "wort"-Felder diakritika-freie Formen.
    # Hier ersetzen wir sie durch die Originalformen aus norm_to_original.
    for comp in greek_composita:
        w_key = comp.get("wort", "").lower()
        original = norm_to_original.get(w_key)
        if original:
            comp["wort"] = original

    for w in words_normalized:
        if w in _GR_FUNC_NORMALIZED or len(w) <= 2:
            function_word_freq[w] += 1
        else:
            content_word_freq[w] += 1

    # C3-FIX (v59.8): Bigramme/Trigramme MIT Originalformen (Diakritika)
    # Vorher: _extract_ngrams(words_normalized) → "μεν αρ" (unlesbar)
    # Jetzt: Originalformen aus norm_to_original, Fallback auf normalisiert
    bigrams = _extract_ngrams(words_normalized, n=2, min_freq=2)
    trigrams = _extract_ngrams(words_normalized, n=3, min_freq=2)

    # D3-FIX (v59.9): Funktionswort-Bigramme herausfiltern.
    # Vorher: „μὲν ἄρ" (2x) — zwei Partikel, kein semantisches Bigramm.
    # Jetzt: Bigramme, bei denen BEIDE Wörter Funktionswörter sind,
    # werden herausgefiltert. Nur Bigramme mit mindestens einem
    # Inhaltswort werden angezeigt.
    def _is_function_bigram(gram_str: str) -> bool:
        """Prüft ob alle Wörter im Gram Funktionswörter sind."""
        parts = gram_str.split()
        return all(p in _GR_FUNC_NORMALIZED or len(p) <= 2 for p in parts)

    bigrams = [(g, c) for g, c in bigrams if not _is_function_bigram(g)]
    trigrams = [(g, c) for g, c in trigrams if not _is_function_bigram(g)]

    # Bigramme in Originalform umwandeln
    bigrams_original = []
    for gram_str, count in bigrams:
        parts = gram_str.split()
        original_parts = [norm_to_original.get(p, p) for p in parts]
        bigrams_original.append((" ".join(original_parts), count))
    trigrams_original = []
    for gram_str, count in trigrams:
        parts = gram_str.split()
        original_parts = [norm_to_original.get(p, p) for p in parts]
        trigrams_original.append((" ".join(original_parts), count))

    result = {
        "source_label": source_label, "language_detected": "grc",
        "text_length_chars": len(text), "text_length_words": total_words,
        "sentence_count": total_sentences,
        "sentence_stats": {"avg_length": avg_sentence_length, "median_length": median_sentence_length, "max_length": max_sentence_length, "min_length": min_sentence_length},
        "sentence_types": sentence_types,
        "type_token_ratio": ttr, "sttr": round(_standardized_ttr(words_normalized, segment_size=100), 3), "morphological_complexity": morph_complexity,
        "punctuation": {"Komma": comma_count, "Punkt": period_count, "Fragezeichen": question_count},
        # B10-FIX: top_content_words mit Originalformen (Diakritika)
        "top_content_words": [
            (norm_to_original.get(w, w), cnt)
            for w, cnt in content_word_freq.most_common(10)
        ],
        "top_function_words": function_word_freq.most_common(5),
        "bigrams": bigrams_original[:5], "trigrams": trigrams_original[:5],
        "paragraph_stats": paragraph_stats,
        "hotspot_sentences": hotspot_sentences,
        "composita": greek_composita,              # v59.6: Komposita / Wortschöpfungen
        "verse_structure": {"is_likely_verse": lyrik_signal == "stark", "avg_words_per_line": round(avg_words_per_verse, 1), "stdev_words_per_line": stdev_words_per_verse, "line_count": len(verses), "signal_strength": lyrik_signal},
        "verse_detail": verse_detail,
        "note": "Altgriechisch-Analyse (polytonisch). B4-B7-Fix: Versgrenzen, Silben, Enjambement, NS/Gem, Vokalechos, Klangfiguren aktiv.",
    }
    # Claude-Audit-Fix: Abschluss-Log für _analyze_greek(), damit QUELLE 4
    # in der Terminal-Ausgabe erscheint. Vorher: return dict ohne Log.
    logger.info(
        f"📊 Etappe 1 abgeschlossen: {source_label} — "
        f"{total_words} Wörter, {total_sentences} Sätze, "
        f"TTR={ttr:.3f}, Morph={morph_complexity}, "
        f"Verse={len(verses)}, Lyrik={lyrik_signal}, "
        f"HS/NS/Gem={sentence_types['HS']}/{sentence_types['NS']}/{sentence_types['gemischt']}"
    )
    return result
# ── ENDE ALTGRIECHISCH-SUPPORT ────────────────────────────────────


# ── ALTHEBRÄISCH-SUPPORT (Patch #7b) ──────────────────────────────
# Isolierter Pfad für biblisches Hebräisch. Wird nur aktiviert,
# wenn >50% der Zeichen im hebräischen Unicode-Bereich liegen.

_HEBREW_UNICODE_RANGES = re.compile(
    r'[\u0590-\u05FF]'  # Hebrew block
)

# Sof Pasuq (Versende) und andere hebräische Interpunktion
_SOF_PASUQ = '\u05C3'      # ׃ Versende
_PASEQ = '\u05C0'          # ׀ Trenner
_MAQAF = '\u05BE'          # ־ Bindestrich

def _is_hebrew_text(text: str, threshold: float = 0.3) -> bool:
    """Prüft ob Text überwiegend hebräisch ist.
    
    v59.3-fix: NFD-Normalisierung + Te'amim-Entfernung vor Zählung,
    damit Vokalpunkte/Kantillationszeichen die Zählung nicht verfälschen.
    Threshold 0.3 statt 0.5, damit Metadata-Dilution den Dispatch nicht blockiert.
    Symmetrisch zu _is_greek_text() Fix.
    """
    if not text.strip():
        return False
    import unicodedata
    # NFD-Zerlegung: Kombinierte Zeichen → Basisbuchstabe + Diakritika
    nfd = unicodedata.normalize('NFD', text)
    # Entferne Te'amim (Kantillationszeichen U+0591-U+05AF) und Niqqud (Vokalpunkte)
    # Te'amim sind Category Mn (combining marks), Niqqud ebenfalls
    # Behalte: Konsonanten (U+05D0-U+05EA), Dagesh (U+05BC), Maqaf (U+05BE)
    base_chars = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    hebrew_chars = len(_HEBREW_UNICODE_RANGES.findall(base_chars))
    # alpha_chars: Hebräisch + Latein + Griechisch + Kyrillisch (symmetrisch zu Greek)
    alpha_chars = len(re.findall(r'[a-zA-Z\u0370-\u03FF\u1F00-\u1FFF\u0400-\u04FF\u0590-\u05FF]', base_chars))
    return (hebrew_chars / max(alpha_chars, 1)) >= threshold

def _strip_te_amim(word: str) -> str:
    """Entfernt Kantillationszeichen (Te'amim) für saubere Tokenisierung.
    Behält Konsonanten, Niqqud (Vokalpunkte) und Dagesh."""
    import unicodedata
    nfd = unicodedata.normalize('NFD', word)
    # Te'amim liegen im Bereich U+0591-U+05AF
    stripped = ''.join(c for c in nfd if not ('\u0591' <= c <= '\u05AF'))
    return unicodedata.normalize('NFC', stripped)

def _tokenize_hebrew(text: str) -> list[str]:
    """Tokenisierung für althebräische Texte.
    Behandelt Maqaf (־) als Worttrenner, entfernt Te'amim."""
    # Ersetze Maqaf durch Leerzeichen (Worttrennung)
    normalized = text.replace(_MAQAF, ' ')
    # Splitte an Whitespace
    raw_tokens = re.split(r"\s+", normalized)
    tokens = []
    for tok in raw_tokens:
        tok = tok.strip()
        if not tok:
            continue
        # Entferne Kantillationszeichen
        clean_tok = _strip_te_amim(tok)
        # Entferne angehängte Interpunktion (׃ am Wortende)
        clean_tok = clean_tok.rstrip(_SOF_PASUQ + _PASEQ + ',.;:!?')
        if clean_tok:
            tokens.append(clean_tok)
    return tokens

def _split_sentences_hebrew(text: str) -> list[str]:
    """Satzsegmentierung für Althebräisch.
    Sof Pasuq (׃) = Satz-/Versende. Paseq (׀) = Nebentrenner."""
    # Ersetze Sof Pasuq durch Standard-Satzende
    normalized = text.replace(_SOF_PASUQ, '.')
    # Paseq als schwächeren Trenner behandeln (optional: als Komma)
    normalized = normalized.replace(_PASEQ, ',')
    # Segmentiere an . ? !
    sentences = re.split(r'(?<=[.?!])\s+', normalized)
    return [s.strip() for s in sentences if s.strip()]

def _detect_parallelism(lines: list[str], tokens_per_line: list[int]) -> dict:
    """Einfache Parallelismus-Heuristik für hebräische Poesie.
    Zählt Zeilenpaare mit ähnlicher Länge als potenzielle Parallelismen."""
    parallel_pairs = 0
    total_pairs = 0
    for i in range(len(tokens_per_line) - 1):
        if tokens_per_line[i] > 0 and tokens_per_line[i + 1] > 0:
            ratio = min(tokens_per_line[i], tokens_per_line[i + 1]) / \
                    max(tokens_per_line[i], tokens_per_line[i + 1])
            if ratio >= 0.6:  # Ähnliche Länge → potenzieller Parallelismus
                parallel_pairs += 1
            total_pairs += 1
    
    return {
        "parallel_pairs": parallel_pairs,
        "total_adjacent_pairs": total_pairs,
        "parallelism_ratio": round(parallel_pairs / max(total_pairs, 1), 2),
    }

def _analyze_hebrew(text: str, source_label: str = "Quelle") -> dict:
    """Vollständige Etappe-1-Analyse für althebräische Texte."""
    sentences = _split_sentences_hebrew(text)
    words = _tokenize_hebrew(text)
    
    total_words = len(words)
    total_sentences = len(sentences)
    
    # B2-Fix: Echte Satzstatistiken statt avg für alle 4 Werte (Kimi B2)
    sentence_lengths = [len(_tokenize_hebrew(s)) for s in sentences]
    sentence_lengths_sorted = sorted(sentence_lengths) if sentence_lengths else [0]
    avg_sentence_length = round(sum(sentence_lengths) / max(len(sentence_lengths), 1), 1)
    median_sentence_length = round(sentence_lengths_sorted[len(sentence_lengths_sorted) // 2], 1)
    max_sentence_length = max(sentence_lengths) if sentence_lengths else 0
    min_sentence_length = min(sentence_lengths) if sentence_lengths else 0
    
    # TTR
    unique_words = set(words)
    ttr = round(len(unique_words) / max(total_words, 1), 3)
    
    # B3-Fix: Echte STTR statt TTR-Kopie (Kimi B3)
    sttr = round(_standardized_ttr(words, segment_size=100), 3)
    
    # Morphologische Komplexität (Heuristik: Anteil langer Wörter)
    long_words = sum(1 for w in words if len(w) > 6)
    morph_complexity = round((long_words / max(total_words, 1)) * 10, 1)
    
    # Interpunktion
    sof_pasuq_count = text.count(_SOF_PASUQ)
    paseq_count = text.count(_PASEQ)
    maqaf_count = text.count(_MAQAF)
    
    # Lyrik-Signal & Parallelismus
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    line_tokens = [len(_tokenize_hebrew(l)) for l in lines]
    avg_line_length = sum(line_tokens) / max(len(line_tokens), 1)
    lyrik_signal = "stark" if avg_line_length < 10 and len(lines) > 8 else "schwach"
    line_count = len(lines)
    parallelism = _detect_parallelism(lines, line_tokens)
    
    result = {
        "source_label": source_label, "language_detected": "heb",
        "text_length_chars": len(text), "text_length_words": total_words,
        "sentence_count": total_sentences,
        "sentence_stats": {"avg_length": avg_sentence_length, "median_length": median_sentence_length, "max_length": max_sentence_length, "min_length": min_sentence_length},
        "sentence_types": {"HS": total_sentences, "NS": 0, "gemischt": 0},
        "type_token_ratio": ttr, "sttr": sttr, "morphological_complexity": morph_complexity,
        "punctuation": {"Komma": 0, "Punkt": sof_pasuq_count, "Fragezeichen": 0},
        "top_content_words": [], "top_function_words": [], "bigrams": [], "trigrams": [],
        "paragraph_stats": {"count": 1, "avg_chars": len(text), "min_chars": len(text), "max_chars": len(text), "length_variance": 0},
        "hotspot_sentences": [],
        "composita": _extract_composita(words, sentences, max_items=10, language="he"),  # v59.6: Komposita
        "verse_structure": {"is_likely_verse": lyrik_signal == "stark", "avg_words_per_line": avg_line_length, "stdev_words_per_line": 0, "line_count": line_count, "signal_strength": lyrik_signal},
        "verse_detail": {**_get_empty_verse_detail(), "parallelism": parallelism},  # v59.3-fix (Kimi B1): Null-Struktur + Parallelismus
        "note": "Althebräisch-Analyse. Keine Silbenmetrik – Parallelismus als poetisches Maß.",
    }
    # Claude-Audit-Fix: Abschluss-Log für _analyze_hebrew() (symmetrisch zu Greek).
    # Format konsistent mit Standard-Pfad (f-string, Emoji, mdash).
    logger.info(
        f"📊 Etappe 1 abgeschlossen: {source_label} — "
        f"{total_words} Wörter, {total_sentences} Sätze, "
        f"TTR={ttr:.3f}, Morph={morph_complexity}"
    )
    return result
# ── ENDE ALTHEBRÄISCH-SUPPORT ────────────────────────────────────



def _split_sentences(text: str) -> List[str]:
    """
    Robuste Satz-Segmentierung für deutsche Texte.

    Berücksichtigt:
    - Abkürzungen (z.B., u.a., etc., Dr., Prof., vgl., s.o.)
    - Verschachtelte Satzzeichen (»...«, "...", –)
    - Nummerierungen (1., 2., 3.)

    Returns:
        Liste nicht-leerer Satz-Strings.
    """
    if not text or not text.strip():
        return []

    # Häufige deutsche Abkürzungen schützen
    abbreviations = [
        r'z\.B\.', r'u\.a\.', r'u\.U\.', r'z\.T\.', r's\.o\.', r's\.u\.',
        r'vgl\.', r'etc\.', r'ca\.', r'evtl\.', r'bzw\.', r'bzw',
        r'Dr\.', r'Prof\.', r'Ing\.', r'Fr\.', r'Hr\.',
        r'\d+\.',  # Nummerierungen wie "1.", "2."
    ]

    protected = text
    placeholder_map = {}
    for i, abbr in enumerate(abbreviations):
        matches = list(re.finditer(abbr, protected))
        for match in reversed(matches):
            placeholder = f"__ABBR{i}_{len(placeholder_map)}__"
            placeholder_map[placeholder] = match.group()
            protected = protected[:match.start()] + placeholder + protected[match.end():]

    # Satzgrenzen erkennen
    # Pattern: Satzzeichen (. ! ?) gefolgt von Grossbuchstabe (Latin ODER Kyrillisch)
    # oder Zeilenende oder Anfuehrungszeichen
    sentence_endings = re.split(
        r'(?<=[.!?])\s+(?=[A-ZÄÖÜА-ЯЁ«»"\'])',
        protected,
    )

    # Placeholders zurückersetzen und bereinigen
    sentences = []
    for s in sentence_endings:
        for placeholder, original in placeholder_map.items():
            s = s.replace(placeholder, original)
        s = s.strip()
        if s and len(s) > 3:  # Mindestlänge: keine Fragmente
            sentences.append(s)

    return sentences


# ==============================================================================
# WORT-ANALYSE
# ==============================================================================

def _tokenize(text: str) -> List[str]:
    """
    Einfache Tokenisierung: Wörter aus Text extrahieren.
    Unterstuetzt Latein + Kyrillisch + weitere Unicode-Schriften.
    Entfernt Interpunktion, behaelt Buchstaben aller Schriften.

    C5-FIX (v59.8): Bindestrich-Komposita werden als EIN Token erfasst
    (z.B. бронзово-острое, двузагнутых-судах). Vorher wurde der Bindestrich
    entfernt → zwei separate Tokens → Komposita-Erkennung fand nichts.
    """
    # Unicode-Buchstaben-Range
    _L = (r'a-zA-ZäöüÄÖÜßáàéèíìóòúù'
          r'\u0400-\u04FF'   # Kyrillisch (Russisch, Ukrainisch, etc.)
          r'\u0500-\u052F'   # Kyrillisch Ergaenzung
          r'\u0370-\u03FF'   # Griechisch
          r'\u1F00-\u1FFF'   # Griechisch Extended (Polytonisch)
          r'\u0590-\u05FF'   # Hebräisch
          )
    # C5-FIX: Erfasse auch Bindestrich-Komposita (Wort-Wort)
    # Pattern: Ein oder mehrere Buchstaben, optional gefolgt von
    # (Bindestrich + ein oder mehrere Buchstaben) ein oder mehrmals
    words = re.findall(
        rf'[{_L}]+(?:-[{_L}]+)*',
        text.lower(),
    )
    return words


def _classify_words(words: List[str]) -> Tuple[List[str], List[str]]:
    """
    Klassifiziert Woerter in Inhaltstwoerter und Funktionswoerter.
    Unterstuetzt Deutsch + Russisch.

    Returns:
        (content_words, function_words) — beide in Kleinschreibung.
    """
    all_stopwords = _DE_FUNCTION_WORDS | _RU_FUNCTION_WORDS
    content = []
    function = []
    for w in words:
        if w.lower() in all_stopwords:
            function.append(w.lower())
        else:
            content.append(w.lower())
    return content, function


def _type_token_ratio(words: List[str]) -> float:
    """
    Type-Token-Ratio (TTR): Verhältnis eindeutiger Wörter zu allen Wörtern.
    Maß für lexikalische Diversität.

    HINWEIS: TTR ist korrelliert mit Textlänge. Für vergleichende
    Aussagen sollte der Text ähnlich lang sein oder STTR verwendet werden.
    """
    if not words:
        return 0.0
    return len(set(words)) / len(words)


def _standardized_ttr(words: List[str], segment_size: int = 100) -> float:
    """
    Standardized Type-Token Ratio (STTR): TTR pro Segment, dann Ø.
    Kompensiert Längeneffekte bei TTR.

    Args:
        words:       Liste aller Wörter
        segment_size: Wörter pro Segment (Standard: 100)
    """
    if len(words) < segment_size:
        return _type_token_ratio(words)

    ttrs = []
    for i in range(0, len(words) - segment_size + 1, segment_size):
        segment = words[i:i + segment_size]
        ttrs.append(_type_token_ratio(segment))

    return sum(ttrs) / len(ttrs) if ttrs else 0.0


def _morphological_complexity(words: List[str]) -> float:
    """
    Proxy für morphologische Komplexität: Mittlere Wortlänge gewichtet
    mit Fremdwort-Anteil (Wörter > 10 Zeichen als Proxy für
    lateinische/fremdsprachige Lexik).

    HINWEIS (AGENTS.md Lektion): Dies misst morphologische Komplexität,
    NICHT Tynjanows "hohe lexikalische Färbung". "Disposition" ist lang
    und lateinisch, aber in Lenins Kontext sofort deflationiert.
    "Dreck" ist kurz und germanisch, aber in einem philosophischen Text
    ein Register-Bruch. Echtes Register-Mapping: v57.5+.
    """
    if not words:
        return 0.0

    avg_length = sum(len(w) for w in words) / len(words)
    long_word_ratio = sum(1 for w in words if len(w) > 10) / len(words)

    # Gewichtete Kombination: Mittlere Länge + Fremdwort-Anteil
    return round(avg_length + (long_word_ratio * 3), 2)


# ==============================================================================
# N-GRAMME
# ==============================================================================

def _extract_ngrams(words: List[str], n: int = 2, min_freq: int = 2) -> List[Tuple[str, int]]:
    """
    Extrahiert N-Gramme mit Mindestfrequenz.

    Args:
        words:    Wortliste (bereits tokenized, lowercase)
        n:        Gram-Größe (2 = Bigramm, 3 = Trigramm)
        min_freq: Mindestfrequenz für Aufnahme

    Returns:
        Liste von (ngram_string, count), absteigend nach Frequenz.
    """
    if len(words) < n:
        return []

    ngrams = []
    for i in range(len(words) - n + 1):
        gram = " ".join(words[i:i + n])
        ngrams.append(gram)

    counter = Counter(ngrams)
    return [(gram, count) for gram, count in counter.most_common(20) if count >= min_freq]


# ==============================================================================
# HOTSPOT-SÄTZE
# ==============================================================================

def _find_hotspot_sentences(
    sentences: List[str],
    top_k: int = 5,
) -> List[Dict]:
    """
    Identifiziert die auffälligsten Sätze eines Textes.

    Kriterien (gewichtet):
    1. Satzlänge (lange Sätze sind komplexer, +30%)
    2. Ungewöhnliche Wortwahl (hoher Anteil seltener Wörter, +25%)
    3. Interpunktions-Dichte (viele Kommas/Strichpunkte, +20%)
    4. Morphologische Komplexität (hoher Fremdwortanteil, +15%)
    5. Kontrast-Marker (aber, jedoch, dennoch, sondern, +10%)

    Returns:
        Liste von Dicts mit 'sentence', 'score', 'reason'.
    """
    if not sentences:
        return []

    # Korpus-weite Worthäufigkeit berechnen (für Seltenheits-Score)
    all_words = []
    for s in sentences:
        all_words.extend(_tokenize(s))
    word_freq = Counter(all_words)
    total_words = len(all_words) if all_words else 1

    # Durchschnittliche Satzlänge
    avg_sent_len = sum(len(_tokenize(s)) for s in sentences) / len(sentences) if sentences else 1

    # Kontrast-Marker (Deutsch + Russisch)
    contrast_markers = frozenset({
        "aber", "jedoch", "dennoch", "sondern", "allerdings", "freilich",
        "trotzdem", "gleichwohl", "hingegen", "andererseits", "indessen",
        # Russische Kontrast-Marker
        "но", "однако", "а", "зато", "впрочем", "напротив", "же",
    })

    scored = []
    for sent in sentences:
        words = _tokenize(sent)
        if not words:
            continue

        score = 0.0
        reasons = []

        # 1. Satzlängen-Score (Abweichung nach oben)
        length_ratio = len(words) / avg_sent_len if avg_sent_len > 0 else 1
        if length_ratio > 1.3:
            score += 0.30
            reasons.append("langer Satz")
        elif length_ratio > 1.1:
            score += 0.15
            reasons.append("überdurchschnittlich lang")

        # 2. Seltenheits-Score (Anteil seltener Wörter)
        rare_threshold = max(2, total_words // 200)  # Wörter mit freq ≤ Threshold sind "selten"
        rare_count = sum(1 for w in words if word_freq.get(w, 0) <= rare_threshold)
        rare_ratio = rare_count / len(words) if words else 0
        if rare_ratio > 0.4:
            score += 0.25
            reasons.append("viele seltene Wörter")
        elif rare_ratio > 0.25:
            score += 0.12
            reasons.append("ungewöhnliche Wortwahl")

        # 3. Interpunktions-Dichte
        comma_count = sent.count(",") + sent.count(";") + sent.count("–") + sent.count(":")
        punct_density = comma_count / max(len(words), 1)
        if punct_density > 0.25:
            score += 0.20
            reasons.append("hohe Interpunktionsdichte")
        elif punct_density > 0.15:
            score += 0.10
            reasons.append("komplexe Interpunktion")

        # 4. Morphologische Komplexität im Satz
        morph = _morphological_complexity(words)
        if morph > 7.0:
            score += 0.15
            reasons.append("hohe morph. Komplexität")
        elif morph > 5.5:
            score += 0.07
            reasons.append("erhöhte morph. Komplexität")

        # 5. Kontrast-Marker
        word_set = set(w.lower() for w in words)
        if word_set & contrast_markers:
            score += 0.10
            reasons.append("Kontrast-Marker")

        scored.append({
            "sentence": sent,
            "score": round(score, 3),
            "reasons": reasons,
        })

    # Top-K nach Score
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


# ==============================================================================
# KOMPOSITA / WORTSCHÖPFUNGEN (v59.6)
# ==============================================================================
# Systematische Extraktion von zusammengesetzten Wörtern pro Quelle.
# Vorher fehlte diese Datensammlung komplett — die HRE musste Komposita
# mühsam aus Hotspot-Sätzen heraussuchen. Jetzt liefert Etappe 1 eine
# eigene Liste mit Kontext (Satz) für jedes Kompositum.

# Russische Präfixe die typischerweise Komposita einleiten
_RU_COMPOUND_PREFIXES = (
    'дву', 'двух', 'много', 'сверх', 'полу', 'анти', 'меж', 'обще',
    'пред', 'после', 'макро', 'микро', 'гипер', 'гипо', 'супер',
    'экстра', 'ультра', 'архи', 'контр', 'нео', 'псевдо', 'квази',
    'пан', 'транс', 'интер', 'суб', 'инфра', 'аэро', 'аква',
    'био', 'гео', 'нефте', 'газо', 'электро', 'фото', 'кино',
    'металло', 'стекло', 'железо', 'чугуно', 'камне', 'древо',
    'серно', 'бронзо', 'злато', 'серебро', 'медно', 'стально',
    # D4-FIX (v59.9): Produktive Adverb-о-Verbindungselemente für russische
    # Übersetzungen von Homer. Мuster: Adverb(-о) + Adjektivwurzel.
    # Diese Komposita sind in poetischen Übersetzungen extrem häufig:
    # пышнокудрая, богаторогатого, темноносый, двузагнутых etc.
    'темно',   # темно-носый (dunkel-nasig), темно-карий etc.
    'пышно',   # пышно-кудряя (üppig-lockig)
    'быстро',  # быстро-ходный
    'широко',  # широко-плечий
    'высоко',  # высоко-горный
    'длинно',  # длинно-ногий
    'мало',    # мало-кровный
    'тонко',   # тонко-ногий
    'прямо',   # прямо-линейный
    'легко',   # легко-крылый
    'тяжело',  # тяжело-весный
    'густо',   # густо-лиственный
    'остро',   # остро-зубый
    'кудряво', # кудряво-волосый
    'светло',  # светло-лицый
    'тихо',    # тихо-звучный
    'ясно',    # ясно-звучный
    'чисто',   # чисто-сердечный
    'слепо',   # слепо-верящий
    'гладко',  # гладко-ствольный
    'коротко', # коротко-хвостый
    'толсто',  # толсто-ствольный
    'крепко',  # крепко-нервный
    'сладко',  # сладко-звучный
    'богато',  # богато-рогатый (reicbbes Geweih)
    'ровно',   # ровно-стенный
    'кругло',  # кругло-лицый
    'бело',    # бело-снежный
    'черно',   # черно-ноский
    'красно',  # красно-речивый
    'сильно',  # сильно-действующий
)

# Deutsche Präfixe die Komposita einleiten (Spec v59.6).
# Mindestlänge 10 Zchn + Stoppliste + Doppelpräfix-Filter (siehe _extract_composita).
_DE_COMPOUND_PREFIXES = (
    'be', 'ge', 'er', 'ver', 'zer', 'ent', 'emp', 'miss',
    'über', 'unter', 'durch', 'hinter', 'wieder', 'wider', 'hinterher',
)

# Deutsche Stoppliste für Komposita-Erkennung (Spec v59.6 + Erweiterung).
# Wörter in dieser Liste werden NIE als Komposita gemeldet, auch wenn sie die
# Präfix-/Längen-Heuristik erfüllen würden. Lower-cased gespeichert, Lower-Vergleich.
_COMPOSITA_STOPLIST_DE = frozenset({
    # Spec-Liste (dedupliziert)
    'beispielsweise', 'veranschaulichen', 'ausreichend', 'außerdem',
    'insbesondere', 'unmittelbar', 'wahrscheinlich', 'mittlerweile',
    'überdies', 'jedenfalls', 'notwendigerweise', 'selbstverständlich',
    'fraglicherweise', 'zweifellos', 'hinsichtlich', 'hervorragend',
    'unumgänglich',
    # Erweiterung: häufige ver-/er-/be-/ge-Wörter die keine Komposita sind
    'verbindung', 'verhältnis', 'verstehen', 'erklärung',
    'begriff', 'beziehung', 'bedeutung', 'ergebnis',
    'verfahren', 'verlauf', 'versuch', 'entscheidung',
    'erfahrung', 'erinnerung', 'erwartung', 'beobachtung',
    'benutzung', 'benennung', 'gebrauch', 'gedanke',
    'gegend', 'gelingen', 'gelegenheit', 'gemälde',
})

# Griechische Komposita-Marker (Präpositionen/Präfixe die Komposita bilden).
# Bestehende Liste + Spec-Ergänzungen v59.6 (akzent-normalisiert).
_GR_COMPOUND_PREFIXES = (
    'συν', 'δια', 'επι', 'υπερ', 'υπο', 'περι', 'απο', 'κατα',
    'ανα', 'παρα', 'προ', 'μετα', 'αντι', 'αρχ', 'δωρ',
    'χρυσο', 'αργυρ', 'σιδηρ', 'χαλκο', 'λιθο',
    # Spec v59.6 Ergänzungen (akzent-normalisiert, ohne Akzent verglichen)
    'εκ', 'εξ', 'προς',
    # D5-FIX (v59.9): ἀμφι fehlte — ἀμφοτέρωθεν (von beiden Seiten)
    # ist ein typisches Homer-Kompositum.
    'αμφι', 'αμφοτερο',
    # D5-FIX: Weitere produktive griechische Komposita-Präfixe
    'φιλο',    # φιλο-σοφος, φιλο-τιμος
    'πολυ',    # πολυ-τροπος, πολυ-μητις
    'παν',     # παν-τοπος, παν-ουργος
    'ομο',     # ομο-νοια, ομο-φωνος
    'εθνο',    # εθνο-λογος
    'θειο',    # θειο-τροπος
    'νεο',     # νεο-λογισμος
    'πρωτο',   # πρωτο-πορος
    'γερωντο', # γερωντο-κομος
    'ιππο',    # ιππο-ποταμος
    'μισο',    # μισο-πουλος
    'μακρο',   # μακρο-σκελης
    'μικρο',   # μικρο-ψυχος
)


def _extract_composita(
    words: List[str],
    sentences: List[str],
    max_items: int = 15,
    language: str = "auto",
) -> List[Dict]:
    """
    Identifiziert zusammengesetzte Wörter (Komposita / Wortschöpfungen).

    Strategien (sprachabhängig):
    DE: Bindestrich + Präfix + lang (>=14 Zchn) + Stopliste + Acro-Filter
    EL: Präfix (akzent-normalisiert) + lang (>=12 Zchn)
    HE: Maqqef-Verbindungen + lang (>=10 Zchn)
    RU: Präfix + lang (>=14 Zchn) — unangetastet unter 'auto'

    Rückgabe-Felder (deutsch, Spec v59.6):
        wort, typ, laenge, kontext (<=150 Zchn), bestandteile, haeufigkeit

    Typ-Werte: bindestrich, praefix, lang, greek_praefix, hebrew_maqqef
    """
    if not words:
        return []

    # ── Hilfsfunktion: Akzent-Normalisierung für Griechisch ──
    def _strip_greek_accents(s: str) -> str:
        import unicodedata
        return ''.join(
            c for c in unicodedata.normalize('NFD', s)
            if unicodedata.category(c) != 'Mn'
        )

    # ── Hilfsfunktion: Acro-Heuristik ──
    def _is_acronym(w: str) -> bool:
        """Wort mit >=3 Zchn, >=80% Großbuchstaben, kein Kleinbuchstabe."""
        if len(w) < 3:
            return False
        upper_count = sum(1 for c in w if c.isupper())
        has_lower = any(c.islower() for c in w)
        return upper_count / len(w) >= 0.8 and not has_lower

    # ── Satzzuordnung: Welches Wort steht in welchem Satz? ──
    word_to_sentence = {}
    for sent in sentences:
        sent_lower = sent.lower()
        for w in words:
            if w.lower() in sent_lower and w not in word_to_sentence:
                word_to_sentence[w] = sent

    composita = {}  # word_lower → Dict (dedupliziert, Häufigkeit)
    word_counts = Counter(w.lower() for w in words)  # für Häufigkeit

    # ── DEUTSCH: Bindestrich-Komposita ──
    if language in ("de", "auto"):
        for w in words:
            w_lower = w.lower()
            if '-' in w and len(w) > 4:
                parts = w.split('-')
                # Ziffern-Komposita ausschließen (3-Zimmer-Wohnung)
                if any(p.isdigit() for p in parts):
                    continue
                # Mindestens 2 Zeichen auf jeder Seite
                if all(len(p) >= 2 for p in parts) and len(parts) >= 2:
                    # Konjunktionen ausschließen (und-oder)
                    if all(p.lower() in ('und', 'oder', 'bzw', 'resp') for p in parts):
                        continue
                    # Acro-Filter: BRD-Staat → raus
                    if any(_is_acronym(p) for p in parts):
                        continue
                    key = w_lower
                    composita[key] = {
                        "wort": w,
                        "typ": "bindestrich",
                        "laenge": len(w),
                        "kontext": word_to_sentence.get(w, "")[:150],
                        "bestandteile": parts,
                        "haeufigkeit": word_counts.get(w_lower, 1),
                    }

    # ── B14-FIX (v59.7): RUSSISCH: Bindestrich-Komposita ──
    # Vorher fehlten kyrillische Bindestrich-Komposita komplett.
    # Žukovskij: бронзово-острое, темноносый, двузагнутых etc.
    # DE-Bindestrich-Pfad greift nicht, weil language="auto" nur "de"
    # prüft und kyrillische Wörter nicht als DE erkannt werden.
    if language in ("ru", "auto"):
        for w in words:
            w_lower = w.lower()
            if w_lower in composita:
                continue
            # Kyrillischer Bindestrich: enthält '-' UND kyrillische Zeichen
            has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in w)
            if '-' in w and has_cyrillic and len(w) > 4:
                parts = w.split('-')
                if len(parts) >= 2 and all(len(p) >= 2 for p in parts):
                    # Ziffern-Komposita ausschließen
                    if any(p.isdigit() for p in parts):
                        continue
                    composita[w_lower] = {
                        "wort": w,
                        "typ": "bindestrich",
                        "laenge": len(w),
                        "kontext": word_to_sentence.get(w, "")[:150],
                        "bestandteile": parts,
                        "haeufigkeit": word_counts.get(w_lower, 1),
                    }

    # ── DEUTSCH: Präfix-Komposita ──
    if language in ("de", "auto"):
        for w in words:
            w_lower = w.lower()
            # Acro-Filter: BRD-Staat → raus
            if '-' in w:
                parts = w.split('-')
                if any(_is_acronym(p) for p in parts):
                    continue
            if w_lower in composita:
                continue
            # Stopliste
            if w_lower in _COMPOSITA_STOPLIST_DE:
                continue
            for prefix in _DE_COMPOUND_PREFIXES:
                if w_lower.startswith(prefix):
                    # Kurze Präfixe (≤3 Zchn) brauchen längere Wörter,
                    # sonst Fehlalarme wie "begleite" = be+gleite.
                    min_word_len = 10 if len(prefix) <= 3 else len(prefix) + 4
                    if len(w) < min_word_len:
                        continue
                    if len(w) <= len(prefix) + 3:
                        continue
                    composita[w_lower] = {
                        "wort": w,
                        "typ": "praefix",
                        "laenge": len(w),
                        "kontext": word_to_sentence.get(w, "")[:150],
                        "bestandteile": [],
                        "haeufigkeit": word_counts.get(w_lower, 1),
                    }
                    break

    # ── RUSSISCH: Präfix-Komposita (unangetastet unter 'auto') ──
    if language in ("ru", "auto"):
        for w in words:
            w_lower = w.lower()
            if w_lower in composita:
                continue
            for prefix in _RU_COMPOUND_PREFIXES:
                if w_lower.startswith(prefix) and len(w) > len(prefix) + 3:
                    composita[w_lower] = {
                        "wort": w,
                        "typ": "praefix",
                        "laenge": len(w),
                        "kontext": word_to_sentence.get(w, "")[:150],
                        "bestandteile": [],
                        "haeufigkeit": word_counts.get(w_lower, 1),
                    }
                    break

    # ── GRIECHISCH: Präfix-Komposita (akzent-normalisiert) ──
    if language in ("el", "auto"):
        for w in words:
            w_lower = w.lower()
            w_norm = _strip_greek_accents(w_lower)
            if w_lower in composita:
                continue
            for prefix in _GR_COMPOUND_PREFIXES:
                prefix_norm = _strip_greek_accents(prefix)
                if w_norm.startswith(prefix_norm) and len(w) > len(prefix) + 3:
                    composita[w_lower] = {
                        "wort": w,
                        "typ": "greek_praefix",
                        "laenge": len(w),
                        "kontext": word_to_sentence.get(w, "")[:150],
                        "bestandteile": [],
                        "haeufigkeit": word_counts.get(w_lower, 1),
                    }
                    break

    # ── HEBRÄISCH: Maqqef-Verbindungen ──
    if language == "he":
        for w in words:
            w_lower = w.lower()
            # Maqqef (U+05BE) oder ASCII-Hyphen in hebräischen Wörtern
            if ('־' in w or '-' in w) and len(w) > 3:
                # Prüfe ob hebräische Buchstaben vorhanden
                has_hebrew = any('\u0590' <= c <= '\u05FF' for c in w)
                if has_hebrew:
                    parts = w.replace('־', '-').split('-')
                    if all(len(p) >= 2 for p in parts):
                        composita[w_lower] = {
                            "wort": w,
                            "typ": "hebrew_maqqef",
                            "laenge": len(w),
                            "kontext": word_to_sentence.get(w, "")[:150],
                            "bestandteile": parts,
                            "haeufigkeit": word_counts.get(w_lower, 1),
                        }

    # ── LANGE WÖRTER (alle Sprachen) ──
    length_threshold = 12  # Deutsch (Klangführung = 12 Zchn), Russisch
    if language == "el":
        length_threshold = 12
    elif language == "he":
        length_threshold = 10

    words_by_length = sorted(set(words), key=len, reverse=True)
    for w in words_by_length:
        w_lower = w.lower()
        if w_lower in composita:
            continue
        if len(w) >= length_threshold:
            # Acro-Filter
            if _is_acronym(w):
                continue
            # Stopliste (DE)
            if language in ("de", "auto") and w_lower in _COMPOSITA_STOPLIST_DE:
                continue
            # Nur echte Wörter (Buchstaben oder Bindestrich-Komposita)
            if w.isalpha() or ('-' in w and all(p.isalpha() for p in w.split('-'))):
                composita[w_lower] = {
                    "wort": w,
                    "typ": "lang",
                    "laenge": len(w),
                    "kontext": word_to_sentence.get(w, "")[:150],
                    "bestandteile": [],
                    "haeufigkeit": word_counts.get(w_lower, 1),
                }

    # ── Reklassifikation: sehr lange Präfix-Wörter → lang ──
    # Wörter ≥20 Zchn sind Determinativkomposita, keine Präfixbildungen.
    for key, item in composita.items():
        if item["typ"] == "praefix" and item["laenge"] >= 20:
            item["typ"] = "lang"

    # ── Sortierung: nach Länge absteigend ──
    result = sorted(
        composita.values(),
        key=lambda x: -x["laenge"],
    )

    # ── Kontext-Bereinigung: nie leer, max 150 Zchn ──
    for item in result:
        if not item['kontext']:
            item['kontext'] = item['wort']
        if len(item['kontext']) > 150:
            item['kontext'] = item['kontext'][:147] + '...'

    return result[:max_items]


# ==============================================================================
# ABSATZSTRUKTUR
# ==============================================================================

def _analyze_paragraphs(text: str) -> Dict:
    """
    Analysiert Absatzstruktur.

    Returns:
        Dict mit: count, avg_chars, min_chars, max_chars, length_variance
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        # Fallback: Ganzer Text als ein Absatz
        return {
            "count": 1,
            "avg_chars": len(text),
            "min_chars": len(text),
            "max_chars": len(text),
            "length_variance": 0,
        }

    lengths = [len(p) for p in paragraphs]
    avg = sum(lengths) / len(lengths)
    variance = sum((l - avg) ** 2 for l in lengths) / len(lengths) if len(lengths) > 1 else 0

    return {
        "count": len(paragraphs),
        "avg_chars": round(avg, 1),
        "min_chars": min(lengths),
        "max_chars": max(lengths),
        "length_variance": round(math.sqrt(variance), 1),  # Standardabweichung
    }



# ==============================================================================
# LYRIK-PROXY: _detect_verse_structure (v58.1)
# ==============================================================================

def _detect_verse_structure(text: str) -> Dict:
    """Heuristische Erkennung von Versstruktur.

    Zwei Signale (Qwen 3.6 + Claude):
    1. avg_words_per_line < 12: Lyrik hat kürzere Zeilen als Prosa
    2. stdev_words_per_line < 3: Lyrik hat gleichmäßigere Zeilen als Prosa

    Keine binäre Klassifikation — das Signal kann Etappe 2 nutzen,
    muss es aber nicht. Die Modus-Erkennung entscheidet final.

    Args:
        text: Der zu analysierende Text.

    Returns:
        Dict mit: is_likely_verse, avg_words_per_line, stdev_words_per_line,
        line_count, signal_strength ("stark"/"mittel"/"kein")
    """
    # B13-FIX (v59.7): Versnummern auf eigenen Zeilen filtern.
    # Russische Hexameter-Übersetzungen (Žukovskij etc.) enthalten oft
    # Versnummern auf eigenen Zeilen (z.B. "87", "88"). Diese werden
    # im Greek-Pfad bereits gefiltert, aber im Standard-Pfad nicht.
    # Das verfälscht avg_words_per_line und line_count → instabile Ergebnisse.
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    # Filtere eigenständige Versnummern (1-4 Ziffern, optional mit Buchstabe)
    lines = [l for l in lines if not re.match(r'^\d{1,4}[a-z]?$', l)]
    if len(lines) < 2:
        return {
            "is_likely_verse": False,
            "avg_words_per_line": 0,
            "stdev_words_per_line": 0,
            "line_count": len(lines),
            "signal_strength": "kein",
        }

    words_per_line = [len(l.split()) for l in lines]
    avg = sum(words_per_line) / len(words_per_line)

    if len(words_per_line) > 1:
        variance = sum((w - avg) ** 2 for w in words_per_line) / len(words_per_line)
        stdev = math.sqrt(variance)
    else:
        stdev = 0.0

    # Signalstärke bestimmen (Claude: beide Signale kombinieren)
    avg_signal = avg < 12   # Qwen 3.6: Prosa typisch >12 Wörter/Zeile
    stdev_signal = stdev < 3  # Claude: Lyrik hat niedrigere Varianz

    if avg_signal and stdev_signal:
        signal_strength = "stark"
        is_likely = True
    elif avg_signal or stdev_signal:
        signal_strength = "mittel"
        is_likely = True
    else:
        signal_strength = "kein"
        is_likely = False

    return {
        "is_likely_verse": is_likely,
        "avg_words_per_line": round(avg, 1),
        "stdev_words_per_line": round(stdev, 1),
        "line_count": len(lines),
        "signal_strength": signal_strength,
    }

# ==============================================================================
# LYRIK-ANALYTIK: Strophen, Reim, Klang, Enjambement, Rhythmus (v58.2)
# ==============================================================================
# Nur aktiviert wenn LYRIK-SIGNAL ≥ "mittel". Kein Einfluss auf Prosa-Tests.

def _filter_verse_lines(text: str) -> str:
    """B13-FIX (v59.7) + B13b-FIX (v59.9.1): Entfernt Versnummern auf eigenen
    Zeilen und kollabiert entstehende Mehrfach-Leerzeilen.
    
    Russische Hexameter-Übersetzungen (Žukovskij, Šershenevič etc.)
    enthalten oft Versnummern auf eigenen Zeilen (z.B. "87", "135").
    Diese stören Strophen-, Enjambement- und Rhythmuserkennung.
    Im Greek-Pfad werden sie bereits in _detect_greek_verses() gefiltert,
    aber im Standard-Pfad (für russische Übersetzungen) fehlte dieser Filter.
    
    B13b-FIX: Wenn eine Versnummern-Zeile entfernt wird, bleiben die
    umgebenden Leerzeichen stehen → doppelte Leerzeilen → _detect_stanzas()
    splittet an diesen künstlichen Grenzen → 95→114 "Strophen", und die
    Rhythmusklassifikation kippt von "regelmäßig" zu "frei". Der Fix
    kollabiert alle aufeinanderfolgenden Leerzeilen zu einer einzigen.
    
    Args:
        text: Originaltext mit möglichen Versnummern.
    
    Returns:
        Bereinigter Text ohne Versnummernzeilen und ohne Mehrfach-Leerzeilen.
    """
    lines = text.split('\n')
    filtered = []
    for line in lines:
        stripped = line.strip()
        # Eigenständige Versnummern: 1-4 Ziffern, optional mit Buchstabe
        if re.match(r'^\d{1,4}[a-z]?$', stripped):
            continue
        filtered.append(line)
    result = '\n'.join(filtered)
    # B13b-FIX: Mehrfach-Leerzeilen kollabieren
    # Vorher: Vers-Text\n\n87\n\nnächster Vers → Vers-Text\n\n\nnächster Vers
    # Nachher: Vers-Text\n\nnächster Vers (eine Leerzeile = eine Strophengrenze)
    while '\n\n\n' in result:
        result = result.replace('\n\n\n', '\n\n')
    return result


def _detect_stanzas(text: str) -> Dict:
    """Erkennt Strophenstruktur eines Gedichts.

    Strophen = Zeilengruppen, getrennt durch Leerzeilen.
    Liefert Strophenanzahl, Verse pro Strophe, und die Strophentexte.

    Args:
        text: Der zu analysierende Text (Original, nicht bereinigt).

    Returns:
        Dict mit: stanza_count, lines_per_stanza (List[int]),
        stanzas (List[str]), stanza_pattern (z.B. "4-4-4" für drei Quartette)
    """
    # In Strophen aufteilen (Leerzeile = Strophengrenze)
    raw_stanzas = text.split('\n\n')
    stanzas = []
    for s in raw_stanzas:
        lines = [l.strip() for l in s.split('\n') if l.strip()]
        if lines:
            stanzas.append(lines)

    if not stanzas:
        return {
            "stanza_count": 0,
            "lines_per_stanza": [],
            "stanzas": [],
            "stanza_pattern": "",
        }

    lines_per_stanza = [len(s) for s in stanzas]
    stanza_pattern = "-".join(str(n) for n in lines_per_stanza)

    return {
        "stanza_count": len(stanzas),
        "lines_per_stanza": lines_per_stanza,
        "stanzas": ["\n".join(s) for s in stanzas],
        "stanza_pattern": stanza_pattern,
    }


def _normalize_for_rhyme(word: str) -> str:
    """Normalisiert ein Wort für Reim-Vergleich.

    Entfernt Interpunktion, konvertiert zu Kleinbuchstaben,
    entfernt stumme Endungen (dt. -e, russ. -ь/-ъ).
    Gibt die letzten N Zeichen zurück, die für den Reim relevant sind.
    """
    # Interpunktion entfernen
    clean = re.sub(r'[^\w\u0400-\u04FF]', '', word.lower())
    if not clean:
        return ""

    # Stumme Endungen entfernen
    # Deutsch: Endungs-e ist stumm (trage ~ sage)
    if len(clean) > 2 and clean.endswith('e') and clean[-2] not in 'aeiouäöü':
        clean = clean[:-1]
    # Deutsch: -en → -n für unreinen Reim (tragen ~ sagen)
    # (Nur für Vergleich, nicht als echte Normalisierung)
    # Russisch: weiches Zeichen ь und hartes Zeichen ъ sind stumm
    if clean and clean[-1] in 'ьъ':
        clean = clean[:-1]

    return clean


def _detect_rhyme_scheme(text: str) -> Dict:
    """Erkennt Reimpaare und Reimschema.

    Vergleicht Zeilenenden innerhalb jeder Strophe.
    Zwei Zeilen reimen sich, wenn ihre letzten 2-3 Buchstaben
    (nach Normalisierung) übereinstimmen.

    C6-FIX (v59.8): Für griechischen Text wird sofort "Kein Reim" zurück-
    gegeben, da Altgriechisch (Homer etc.) keinen Endreim verwendet.
    Die Standard-Reimerkennung würde nonsensical matches bei
    polytonischem Griechisch produzieren (z.B. Wörter mit gleichen
    Endsilben durch Kasusendungen, nicht durch Reim).

    Args:
        text: Der zu analysierende Text.

    Returns:
        Dict mit: rhyme_pairs, scheme_labels, scheme_notation,
        rhyme_type ("Kreuzreim"/"Paarreim"/"Umarmender Reim"/"Gemischt"/"Kein Reim")
    """
    # C6-FIX: Griechischer Text → sofort "Kein Reim"
    if _is_greek_text(text, threshold=0.15):
        return {
            "rhyme_pairs": [],
            "scheme_labels": [],
            "scheme_notation": "",
            "rhyme_type": "Kein Reim",
            "note": "Altgriech. Epik verwendet keinen Endreim; Reimschema nicht anwendbar.",
        }

    stanzas_raw = text.split('\n\n')
    stanzas = []
    for s in stanzas_raw:
        lines = [l.strip() for l in s.split('\n') if l.strip()]
        if lines:
            stanzas.append(lines)

    if not stanzas:
        return {
            "rhyme_pairs": [],
            "scheme_labels": [],
            "scheme_notation": "",
            "rhyme_type": "Kein Reim",
        }

    all_rhyme_pairs = []
    all_scheme_labels = []

    for stanza_lines in stanzas:
        # Letzte bedeutungstragende Wörter je Zeile extrahieren
        end_words = []
        for line in stanza_lines:
            words = line.split()
            if words:
                end_words.append(_normalize_for_rhyme(words[-1]))
            else:
                end_words.append("")

        # Reim-Vergleich: Je zwei Zeilenenden vergleichen
        n = len(stanza_lines)
        labels = [None] * n
        rhyme_label = ord('A')
        pairs = []

        for i in range(n):
            if labels[i] is not None:
                continue
            if not end_words[i]:
                labels[i] = '.'
                continue

            # Reim-Partner suchen
            for j in range(i + 1, n):
                if labels[j] is not None:
                    continue
                if not end_words[j]:
                    continue

                # Vergleich: letzten 2-3 Zeichen + Vokalgerüst (v59)
                ew_i = end_words[i]
                ew_j = end_words[j]
                is_rhyme = False

                if len(ew_i) >= 2 and len(ew_j) >= 2:
                    # Exakter Reim: letzte 2 Zeichen
                    if ew_i[-2:] == ew_j[-2:]:
                        is_rhyme = True
                    # Längerer Reim: letzte 3 Zeichen (bevorzugen)
                    if len(ew_i) >= 3 and len(ew_j) >= 3 and ew_i[-3:] == ew_j[-3:]:
                        is_rhyme = True

                # v59: Vokalgerüst-Vergleich als 2. Pass
                # Findet Reime, die der Buchstabenvergleich verpasst
                if not is_rhyme:
                    _VOWELS_RHYME = set('aeiouäöüуеыаоэяиюё')
                    vsk_i = ''.join(ch for ch in ew_i if ch in _VOWELS_RHYME)
                    vsk_j = ''.join(ch for ch in ew_j if ch in _VOWELS_RHYME)
                    # Vokalreim: letzte 2 Vokale stimmen überein
                    if len(vsk_i) >= 2 and len(vsk_j) >= 2 and vsk_i[-2:] == vsk_j[-2:]:
                        is_rhyme = True

                # v59.2: Russische-Endungen-Pass als 3. Pass
                # Findet Reime wie "одинокий/далекой" durch Abgleich
                # der Endung nach Abzug typischer Adjektiv-/Partizip-Suffixe
                if not is_rhyme:
                    _RU_ADJ_ENDINGS = [
                        'ий', 'ый', 'ой', 'ая', 'ое', 'ые',
                        'их', 'ых', 'им', 'ым', 'ую', 'ою',
                    ]
                    stem_i = ew_i
                    stem_j = ew_j
                    ending_i_stripped = ""
                    ending_j_stripped = ""
                    for ending in _RU_ADJ_ENDINGS:
                        if stem_i.endswith(ending) and len(stem_i) > len(ending) + 1:
                            ending_i_stripped = ending
                            stem_i = stem_i[:-len(ending)]
                        if stem_j.endswith(ending) and len(stem_j) > len(ending) + 1:
                            ending_j_stripped = ending
                            stem_j = stem_j[:-len(ending)]
                    # Nach Endungs-Strip: Vergleich der übrigen Konsonanz
                    if len(stem_i) >= 2 and len(stem_j) >= 2:
                        if stem_i[-2:] == stem_j[-2:]:
                            is_rhyme = True
                        elif len(stem_i) >= 3 and len(stem_j) >= 3 and stem_i[-3:] == stem_j[-3:]:
                            is_rhyme = True
                        # v59.2: Russische Konsonant-Reime
                        # Wenn beide Endungen typische Adjektiv-Endungen waren
                        # und die Stämme auf denselben Endkonsonanten enden,
                        # ist das ein russischer Konsonant-Reim
                        # (z.B. "одинокий/далекой" → Stämme "одинок/далек" → Endkonsonant "к")
                        elif (ending_i_stripped and ending_j_stripped
                              and stem_i[-1:] == stem_j[-1:]
                              and stem_i[-1:] in 'кстнлрвмпб'):
                            is_rhyme = True

                if is_rhyme:
                    ch = chr(rhyme_label)
                    labels[i] = ch
                    labels[j] = ch
                    rhyme_label += 1
                    pairs.append({
                        "label": ch,
                        "line_a": i + 1,
                        "word_a": stanza_lines[i].split()[-1] if stanza_lines[i].split() else "",
                        "line_b": j + 1,
                        "word_b": stanza_lines[j].split()[-1] if stanza_lines[j].split() else "",
                    })

            # Kein Reim gefunden → freie Zeile
            if labels[i] is None:
                labels[i] = 'x'

        all_rhyme_pairs.extend(pairs)
        all_scheme_labels.extend(labels)
        # v59.1: Strophengrenze in der Notation markieren
        if stanza_lines != stanzas[-1]:  # Nicht nach der letzten Strophe
            all_scheme_labels.append('|')

    # Schema-Notation (v59.1: Strophengrenzen mit | markiert)
    scheme_notation = " ".join(str(l) for l in all_scheme_labels) if all_scheme_labels else ""

    # Reim-Typ bestimmen (pro Strophe)
    # v59.1: Kopie der Labels nehmen, da wir sie beim Typ-Check verbrauchen
    remaining_labels = list(all_scheme_labels)
    rhyme_types = []
    for stanza_lines in stanzas:
        n = len(stanza_lines)
        stanza_labels = remaining_labels[:n]
        remaining_labels = remaining_labels[n:]
        # Strophengrenze überspringen
        if remaining_labels and remaining_labels[0] == '|':
            remaining_labels = remaining_labels[1:]

        if n >= 4:
            a, b, c, d = str(stanza_labels[0]), str(stanza_labels[1]), str(stanza_labels[2]), str(stanza_labels[3])
            if a == c and b == d:
                rhyme_types.append("Kreuzreim")
            elif a == b and c == d:
                rhyme_types.append("Paarreim")
            elif a == d and b == c:
                rhyme_types.append("Umarmender Reim")
            else:
                rhyme_types.append("Gemischt")
        else:
            rhyme_types.append("Gemischt")

    # Dominanter Reim-Typ
    from collections import Counter as _Counter
    type_counts = _Counter(rhyme_types)
    dominant_type = type_counts.most_common(1)[0][0] if type_counts else "Kein Reim"

    # Wenn kaum Reimpaare gefunden → "Kein Reim"
    if len(all_rhyme_pairs) < 2:
        dominant_type = "Kein Reim"

    return {
        "rhyme_pairs": all_rhyme_pairs,
        "scheme_labels": all_scheme_labels,
        "scheme_notation": scheme_notation,
        "rhyme_type": dominant_type,
    }


def _extract_vowel_skeleton(text: str) -> List[Dict]:
    """Extrahiert das Vokalgerüst jeder Zeile.

    Das Vokalgerüst ist die Folge der Vokale einer Zeile als String.
    Es ist das zentrale phonetische Messinstrument für Lyrik:
    - Zeilen mit ähnlichem Vokalgerüst klingen ähnlich
    - Vokalparallelen zwischen Zeilen deuten auf Klangbindung
    - Der Vergleich von Vokalgerüsten ersetzt keine Deutung,
      er liefert aber die Messgröße, die Etappe 2 deuten kann.

    Args:
        text: Der zu analysierende Text.

    Returns:
        Liste von Dicts mit: line, skeleton, words.
        skeleton = Vokal-Sequenz als String (z.B. "ie-e" für "Liebe Seele").
    """
    _VOWELS = set('aeiouäöüуеыаоэяиюё')

    lines_sk = [l.strip() for l in text.split('\n') if l.strip()]
    result = []

    for line_idx, line in enumerate(lines_sk):
        words = re.findall(r'[\w\u0400-\u04FF]+', line.lower())
        if not words:
            continue

        # Vokalgerüst: Vokale aller Wörter, Wortgrenzen mit Bindestrich
        word_skeletons = []
        for w in words:
            w_skel = ''.join(ch for ch in w if ch in _VOWELS)
            if w_skel:
                word_skeletons.append(w_skel)

        if word_skeletons:
            skeleton = '-'.join(word_skeletons)
            result.append({
                "line": line_idx + 1,
                "skeleton": skeleton,
                "words": words,
            })

    return result


def _detect_vowel_echoes(text: str, rhyme_type: str = "Kein Reim") -> Dict:
    """Erkennt Vokal-Echos: Zeilenpaare mit gleichem Endvokal.

    Vokal-Echos sind ein messbares Signal für Klangbindung zwischen
    Zeilen — keine Deutung. Zwei Zeilen mit gleichem Endvokal
    können klanglich verbunden sein, müssen es aber nicht.
    Etappe 2 entscheidet, ob das Echo relevant ist.

    v59.2: Triviale Endvokale werden herausgefiltert.
    Wenn ein Endvokal in >50% der Zeilenenden auftritt (z.B. 'e' im
    Deutschen), sind Echos dieses Vokals statistisch erwartbar und
    tragen keine poetische Information. Sie werden als 'trivial'
    markiert und nicht als Echos ausgegeben. Stattdessen wird eine
    Zusammenfassung geliefert ("X/Y Zeilen enden auf Vokal 'e'").

    v59.3: In Reimgedichten werden Echos mit Abstand ≤ 2 unterdrückt.
    In einem Gedicht mit Kreuzreim ABAB sind Abstand-2-Echos
    strukturbedingt (sie sind der Reim), und Abstand-1-Echos sind
    statistisch erwartbar (nur 2-3 verschiedene Endvokale pro Strophe).
    Sie liefern keine zusätzliche Information über den Klang und
    werden als 'rhyme_structural' markiert.

    Args:
        text: Der zu analysierende Text.
        rhyme_type: Reimschema-Typ aus _detect_rhyme_scheme().
                    Wenn != "Kein Reim", werden Abstand-1/2-Echos gefiltert.

    Returns:
        Dict mit: echoes (List[Dict]), trivial_vowel (str|None),
        trivial_ratio (float), rhyme_filtered (bool).
        echoes = Liste von {line_a, line_b, end_vowel, distance}.
    """
    _VOWELS = set('aeiouäöüуеыаоэяиюё')

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) < 2:
        return {"echoes": [], "trivial_vowel": None, "trivial_ratio": 0.0, "rhyme_filtered": False}

    # Endvokal jeder Zeile bestimmen
    line_end_vowels = []
    for idx, line in enumerate(lines):
        words = re.findall(r'[\w\u0400-\u04FF]+', line.lower())
        end_vowel = None
        if words:
            last_word = words[-1]
            # Letzten Vokal des letzten Worts finden
            for ch in reversed(last_word):
                if ch in _VOWELS:
                    end_vowel = ch
                    break
        line_end_vowels.append({
            "line": idx + 1,
            "end_vowel": end_vowel,
        })

    # v59.2: Trivialen Endvokal bestimmen (dominant in >50% der Zeilen)
    vowel_counts = Counter(
        lev["end_vowel"] for lev in line_end_vowels if lev["end_vowel"]
    )
    total_with_vowel = sum(vowel_counts.values())
    trivial_vowel = None
    trivial_ratio = 0.0
    if total_with_vowel > 0:
        most_common_vowel, most_common_count = vowel_counts.most_common(1)[0]
        trivial_ratio = most_common_count / total_with_vowel
        if trivial_ratio > 0.5:
            trivial_vowel = most_common_vowel

    # Zeilenpaare mit gleichem Endvokal finden
    # v59.2: Triviale Echos ausschließen
    # v59.3: In Reimgedichten Abstand-1/2-Echos unterdrücken (strukturbedingt)
    has_rhyme = rhyme_type != "Kein Reim"
    rhyme_filtered_count = 0
    echoes = []
    for i in range(len(line_end_vowels)):
        if not line_end_vowels[i]["end_vowel"]:
            continue
        for j in range(i + 1, min(i + 6, len(line_end_vowels))):  # Max 5 Zeilen Abstand
            if not line_end_vowels[j]["end_vowel"]:
                continue
            if line_end_vowels[i]["end_vowel"] == line_end_vowels[j]["end_vowel"]:
                # v59.2: Triviale Echos überspringen
                if trivial_vowel and line_end_vowels[i]["end_vowel"] == trivial_vowel:
                    continue
                distance = j - i
                # v59.3: In Reimgedichten Abstand ≤ 2 unterdrücken
                if has_rhyme and distance <= 2:
                    rhyme_filtered_count += 1
                    continue
                echoes.append({
                    "line_a": line_end_vowels[i]["line"],
                    "line_b": line_end_vowels[j]["line"],
                    "end_vowel": line_end_vowels[i]["end_vowel"],
                    "distance": distance,
                })

    # Sortieren: nächste Nachbarn zuerst
    echoes.sort(key=lambda e: e["distance"])
    # v59.9.2 Fix 2026-06-21: echoes[:12] war ein Cap — siehe Kommentar
    # in _detect_greek_vowel_echoes für Details.
    return {
        "echoes": echoes[:50],
        "echoes_count": len(echoes),  # v59.9.2: echte Anzahl
        "trivial_vowel": trivial_vowel,
        "trivial_ratio": round(trivial_ratio, 2),
        "rhyme_filtered": has_rhyme and rhyme_filtered_count > 0,
        "rhyme_filtered_count": rhyme_filtered_count,
    }


def _detect_sound_patterns(text: str) -> Dict:
    """Erkennt Klangfiguren: Alliteration, Assonanz, Binnenreim.

    Arbeitet auf Vers-Ebene (pro Zeile) und sucht nach:
    - Alliteration: Gleicher Anlautkonsonant in Inhaltswörtern (v59: Funktionswörter gefiltert)
    - Assonanz: Gleiche Vokalfolge in Inhaltswörtern (v59: nur Inhaltswörter, min 2 Vokale)
    - Binnenreim: Klanggleichheit innerhalb einer Zeile

    v59-FIX: Funktionswörter ("der","die","das","und",etc.) erzeugen
    trivialerweise Alliterationen und Assonanzen. Sie werden jetzt
    vor dem Matching entfernt. Das reduziert das Rauschen drastisch.

    v59.3-FIXES:
    - Binnenreim: Suffix-Filter nur noch für Nominalsuffixe (-ung, -heit etc.),
      nicht für Adjektivsuffixe (-lich, -isch etc.) — "glücklich/unendlich" ist
      ein echter Binnenreim, kein Grammatik-Artefakt.
    - Alliteration: Zweiter Pass sucht versübergreifende Alliterationen
      (Abstand 1-2 Verse), da kurze Verszeilen oft über Zeilen alliterieren.

    Args:
        text: Der zu analysierende Text.

    Returns:
        Dict mit: alliterations, assonances, internal_rhymes
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    all_function_words = _DE_FUNCTION_WORDS | _RU_FUNCTION_WORDS

    alliterations = []
    assonances = []
    internal_rhymes = []

    _AUX_VERBS = frozenset({
        'hast', 'hat', 'habe', 'haben', 'bin', 'bist', 'sind', 'seid',
        'wird', 'werden', 'wurde', 'wurden', 'kann', 'könnte',
        'muss', 'müsste', 'soll', 'sollte', 'will', 'darf',
        'lässt', 'lassen', 'tue', 'tust', 'tut', 'tun',
        'geht', 'gehst', 'stehen', 'steht', 'liegt', 'liegt',
    })

    def _vowel_pattern(word):
        """Extrahiert Vokal-Folge aus einem Wort."""
        return ''.join(ch for ch in word if ch.lower() in 'aeiouäöüуеыаоэяиюё')

    def _first_consonant(word):
        """Extrahiert den ersten Konsonanten eines Worts für Alliteration."""
        for ch in word:
            if ch.lower() in 'bcdfghjklmnpqrstvwxzбвгджзклмнпрстфхцчшщ':
                return ch.lower()
        return None

    # v59.3: Sammle Inhaltsanfänge pro Zeile für versübergreifende Alliteration
    line_content_initials = []  # [{consonant: [words]}]

    for line_idx, line in enumerate(lines):
        words_all = re.findall(r'[\w\u0400-\u04FF]+', line.lower())
        if len(words_all) < 2:
            line_content_initials.append({})
            continue

        # v59: Inhaltswörter = Wörter, die keine Funktionswörter sind
        content_words = [w for w in words_all if w not in all_function_words and len(w) > 1]

        # --- Alliteration: Gleicher Anlautkonsonant in Inhaltswörtern ---
        # v59.1: Keine Identitätswiederholungen, keine Hilfsverben
        initials = {}
        for w in content_words:
            if not w or w in _AUX_VERBS:
                continue
            fc = _first_consonant(w)
            if fc:
                if fc not in initials:
                    initials[fc] = []
                # v59.1: Gleiche Wörter nicht doppelt zählen
                if w not in initials[fc]:
                    initials[fc].append(w)

        # v59.3: Für versübergreifende Alliteration merken
        line_content_initials.append(initials)

        for consonant, wlist in initials.items():
            if len(wlist) >= 2:
                alliterations.append({
                    "line": line_idx + 1,
                    "consonant": consonant,
                    "words": wlist,
                    "text": line[:80],
                })

        # --- Assonanz: Gleiche Vokalfolge in Inhaltswörtern ---
        # v59: Nur Inhaltswörter, min 2 Vokale im Pattern
        word_vowels = [(w, _vowel_pattern(w)) for w in content_words if len(w) > 2]
        for i in range(len(word_vowels)):
            for j in range(i + 1, min(i + 4, len(word_vowels))):
                w1, v1 = word_vowels[i]
                w2, v2 = word_vowels[j]
                if len(v1) >= 2 and len(v2) >= 2 and v1[:2] == v2[:2] and w1 != w2:
                    assonances.append({
                        "line": line_idx + 1,
                        "vowel_pattern": v1[:2],
                        "word_a": w1,
                        "word_b": w2,
                    })

        # --- Binnenreim: Zwei Wörter in derselben Zeile reimen sich ---
        # v59.1: Deduplizierung — (A,B) und (B,A) zusammenführen
        # v59.3: Suffix-Filter nur für Nominalsuffixe (-ung, -heit etc.)
        # Adjektivsuffixe (-lich, -isch, -bar etc.) erzeugen echte Klangechos
        # und werden NICHT gefiltert — "glücklich/unendlich" ist Poesie, nicht Grammatik.
        _NOUN_SUFFIX_RHYMES = frozenset({
            # Deutsch: Nominalsuffixe
            'ung', 'heit', 'keit', 'tion', 'sion',
            # Russisch: Nominalsuffixe
            'ость', 'ние', 'тие', 'ание', 'ение', 'аться', 'иться',
        })
        seen_rhyme_pairs = set()
        for i in range(len(words_all)):
            for j in range(i + 1, len(words_all)):
                wi = _normalize_for_rhyme(words_all[i])
                wj = _normalize_for_rhyme(words_all[j])
                if len(wi) >= 3 and len(wj) >= 3 and wi[-3:] == wj[-3:] and words_all[i] != words_all[j]:
                    # v59.3: Suffix-Reim nur bei Nominalsuffixen ausschließen
                    is_suffix_rhyme = False
                    for suffix in _NOUN_SUFFIX_RHYMES:
                        if (words_all[i].endswith(suffix) and words_all[j].endswith(suffix)
                                and len(words_all[i]) > len(suffix) + 1
                                and len(words_all[j]) > len(suffix) + 1):
                            stem_i = words_all[i][:-len(suffix)]
                            stem_j = words_all[j][:-len(suffix)]
                            if stem_i != stem_j:
                                is_suffix_rhyme = True
                                break
                    if is_suffix_rhyme:
                        continue
                    # Dedup-Key: alphabetisch sortiertes Paar
                    pair_key = tuple(sorted([words_all[i], words_all[j]]))
                    if pair_key not in seen_rhyme_pairs:
                        seen_rhyme_pairs.add(pair_key)
                        internal_rhymes.append({
                            "line": line_idx + 1,
                            "word_a": words_all[i],
                            "word_b": words_all[j],
                        })

    # --- v59.3: Versübergreifende Alliteration (Abstand 1-2 Verse) ---
    # Kurze Verszeilen alliterieren oft über Zeilengrenzen hinweg.
    # Zweiter Pass: gleicher Anlautkonsonant in Inhaltswörtern benachbarter Zeilen.
    _CONSONANTS = set('bcdfghjklmnpqrstvwxzбвгджзклмнпрстфхцчшщ')
    for dist in (1, 2):
        for i in range(len(lines) - dist):
            j = i + dist
            initials_i = line_content_initials[i] if i < len(line_content_initials) else {}
            initials_j = line_content_initials[j] if j < len(line_content_initials) else {}
            shared_consonants = set(initials_i.keys()) & set(initials_j.keys())
            for consonant in shared_consonants:
                words_i = initials_i[consonant]
                words_j = initials_j[consonant]
                # Gleiche Wörter auf beiden Seiten = Wiederholung, keine Alliteration
                cross_words = [w for w in words_j if w not in words_i]
                if not cross_words:
                    continue
                combined = words_i + cross_words
                # Prüfe: nicht bereits als innerzeilige Alliteration erfasst
                already_found = False
                for existing in alliterations:
                    if (existing.get("consonant") == consonant
                            and existing.get("line") in (i + 1, j + 1)
                            and set(existing.get("words", [])) == set(combined)):
                        already_found = True
                        break
                if not already_found:
                    alliterations.append({
                        "line": i + 1,
                        "line_end": j + 1,
                        "consonant": consonant,
                        "words": combined,
                        "text": f"{lines[i][:40]} | {lines[j][:40]}",
                        "cross_verse": True,
                    })

    # v59.9.1 Fix 2026-06-21: Listen nicht truncaten (war [:20]/[:15]/[:10]).
    # Siehe Kommentar in _detect_greek_sound_patterns für Details.
    return {
        "alliterations": alliterations[:50],  # Cap für Speicher, nicht für Statistik
        "assonances": assonances[:50],
        "internal_rhymes": internal_rhymes[:50],
        "alliterations_count": len(alliterations),  # v59.9.1: echte Anzahl
        "assonances_count": len(assonances),
        "internal_rhymes_count": len(internal_rhymes),
    }


def _detect_enjambement(text: str) -> Dict:
    """Erkennt Enjambements (Zeilensprünge).

    Ein Enjambement liegt vor, wenn ein Sinnzusammenhang
    über eine Zeilengrenze hinweg fortgesetzt wird.
    Heuristik: Zeile endet ohne Satzzeichen, nächste Zeile
    beginnt mit Kleinbuchstabe oder Konjunktion.

    Args:
        text: Der zu analysierende Text.

    Returns:
        Dict mit: enjambements (List[Dict]), count, percentage
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) < 2:
        return {"enjambements": [], "count": 0, "percentage": 0.0}

    # Satzzeichen, die einen Satz abschließen
    sentence_final_punct = set('.!?;:')
    # Konjunktionen, die auf Fortsetzung deuten
    continuation_starters = frozenset({
        # Deutsch
        "und", "oder", "aber", "doch", "denn", "sondern", "als", "wie",
        "die", "der", "das", "den", "dem", "des", "ein",
        # Russisch
        "и", "а", "но", "или", "что", "чтобы", "как", "где", "куда",
    })

    enjambements = []
    for i in range(len(lines) - 1):
        current = lines[i]
        next_line = lines[i + 1]

        if not current or not next_line:
            continue

        # Zeile endet OHNE abschließendes Satzzeichen?
        last_char = current.rstrip()[-1] if current.rstrip() else ''
        ends_without_punct = last_char not in sentence_final_punct

        # Nächste Zeile beginnt mit Kleinbuchstabe oder Konjunktion?
        next_words = next_line.split()
        if not next_words:
            continue
        first_word = re.sub(r'[^\w\u0400-\u04FF]', '', next_words[0])
        starts_continuation = (
            first_word[0].islower() if first_word else False
        ) or first_word.lower() in continuation_starters

        if ends_without_punct and starts_continuation:
            enjambements.append({
                "from_line": i + 1,
                "to_line": i + 2,
                "fragment_a": current[-60:] if len(current) > 60 else current,
                "fragment_b": next_line[:60] if len(next_line) > 60 else next_line,
            })

    total_transitions = len(lines) - 1
    percentage = round(len(enjambements) / total_transitions * 100, 1) if total_transitions > 0 else 0.0

    return {
        "enjambements": enjambements,
        "count": len(enjambements),
        "percentage": percentage,
    }


def _analyze_verse_rhythm(text: str) -> Dict:
    """Analysiert Versrhythmus: Silben pro Vers, Regelmäßigkeit.

    Silbenzählung ist heuristisch (Vokalgruppen = Silben).
    Funktioniert für Deutsch und Russisch.

    Args:
        text: Der zu analysierende Text.

    Returns:
        Dict mit: syllables_per_line, avg_syllables, stdev_syllables,
        is_regular, pattern_description
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return {
            "syllables_per_line": [],
            "avg_syllables": 0,
            "stdev_syllables": 0.0,
            "is_regular": False,
            "pattern_description": "",
        }

    def _count_syllables(word):
        """Heuristische Silbenzählung: Vokalgruppen = Silben."""
        # Vokale: Deutsch + Russisch
        vowels = set('aeiouäöüуеыаоэяиюёAEIOUÄÖУЕЫАОЭЯИЮЁ')
        count = 0
        prev_vowel = False
        for ch in word:
            is_v = ch in vowels
            if is_v and not prev_vowel:
                count += 1
            prev_vowel = is_v
        return max(count, 1)  # Mindestens 1 Silbe

    syllables_per_line = []
    for line in lines:
        words = re.findall(r'[\w\u0400-\u04FF]+', line)
        total = sum(_count_syllables(w) for w in words)
        syllables_per_line.append(total)

    avg = sum(syllables_per_line) / len(syllables_per_line) if syllables_per_line else 0
    variance = sum((s - avg) ** 2 for s in syllables_per_line) / len(syllables_per_line) if len(syllables_per_line) > 1 else 0
    stdev = math.sqrt(variance)

    # Regelmäßigkeit: σ < 1.5 → regelmäßig
    is_regular = stdev < 1.5

    # Metrische Beschreibung
    if is_regular:
        rounded_avg = round(avg)
        if 3 <= rounded_avg <= 5:
            pattern_description = f"Kurzvers ({rounded_avg} Silben)"
        elif 6 <= rounded_avg <= 9:
            pattern_description = f"regelmäßiger Vers ({rounded_avg} Silben)"
        elif 10 <= rounded_avg <= 13:
            pattern_description = f"langer Vers ({rounded_avg} Silben)"
        else:
            pattern_description = f"regelmäßiger Rhythmus ({rounded_avg} Silben)"
    else:
        pattern_description = f"freier Rhythmus (σ {stdev:.1f})"

    return {
        "syllables_per_line": syllables_per_line,
        "avg_syllables": round(avg, 1),
        "stdev_syllables": round(stdev, 1),
        "is_regular": is_regular,
        "pattern_description": pattern_description,
    }


# ==============================================================================
# SATZTYP-ERKENNUNG (HS/NS)
# ==============================================================================

# Interpunktions-Zeichen, die von Woertern entfernt werden vor dem Vergleich
_PUNCT_STRIP = str.maketrans('', '', ',.;:!?("«»—–-…')


def _strip_punct(word: str) -> str:
    """Entfernt haeufige Interpunktionszeichen von einem Wort."""
    return word.translate(_PUNCT_STRIP).strip()


# Mehrwort-Konjunktionen (Russisch + Deutsch) — gegen Satz-String geprueft
_MULTI_WORD_NS = [
    # Russisch
    r'потому\s+что',
    r'оттого\s+что',
    r'так\s+как',
    r'в\s+то\s+время\s+как',
    r'несмотря\s+на\s+то\s+что',
    r'для\s+того\s+чтобы',
    r'с\s+тех\s+пор\s+как',
    r'перед\s+тем\s+как',
    r'после\s+того\s+как',
    r'до\s+того\s+как',
    r'по\s+мере\s+того\s+как',
    r'как\s+только',
    r'как\s+будто',
    r'словно\s+бы',
    r'то\s+лишь',
    # Deutsch
    r'obwohl\s+doch',
    r'auch\s+wenn',
    r'so\s+dass',
]


def _classify_sentence_type(sentence: str) -> str:
    """
    Klassifiziert einen Satz als Hauptsatz (HS) oder Nebensatz (NS).

    Heuristik (vereinfacht):
    - NS: Beginnt mit subordinierender Konjunktion oder Relativpronomen
    - HS: Beginnt mit Verb (Inversion) oder Subjekt + Verb
    - Gemischt: Enthält Komma + Konjunktion

    v57.4.5 FIX: Drei Ursachen fuer NS=0 bei russischen Texten behoben:
    1. Interpunktion an Woertern wurde nicht entfernt ("что," ≠ "что")
    2. Kritische NS-Marker fehlten (который, кто, где, куда, etc.)
    3. Mehrwort-Konjunktionen (потому что, так как, etc.) wurden ignoriert

    HINWEIS: Dies ist eine Heuristik, keine syntaktische Analyse.
    Fehlerquote bei komplexen Schachtelungen: ~15-20%.
    """
    ns_starters = frozenset({
        # Deutsch
        "weil", "da", "obwohl", "obgleich", "während", "bevor", "nachdem",
        "seitdem", "sobald", "falls", "wenn", "dass", "ob", "als",
        "indem", "wodurch", "wobei", "wonach", "weshalb", "weswegen",
        "sodass", "damit", "um",
        # Russische subordinierende Konjunktionen
        "что", "чтобы", "если", "когда", "потому", "поэтому", "поскольку",
        "хотя", "несмотря", "пока", "после", "прежде", "едва", "лишь",
        "раз", "будто", "словно", "точно", "ли",
        # Russische Relativpronomen (v57.4.5: HAEUFIGSTE NS-Einleiter!)
        "который", "которая", "которое", "которые",
        "которого", "которой", "которых", "которым", "которою",
        "которыми", "которую",
        "кто", "кого", "кому", "кем", "ком",
        "чей", "чья", "чьё", "чьи", "чьего", "чьей", "чьих",
        "чьим", "чью", "чьями",
        # Russische subordinierende Adverbien (v57.4.5)
        "где", "куда", "откуда", "зачем", "почему", "сколько",
        "настолько", "поскольку",
    })

    # --- Schritt 1: Erstes Wort (ohne Interpunktion) ---
    raw_words = sentence.split()
    first_word = _strip_punct(raw_words[0]).lower() if raw_words else ""

    if first_word in ns_starters:
        return "NS"

    # --- Schritt 2: Mehrwort-Konjunktionen im Gesamtsatz ---
    sent_lower = sentence.lower()
    for pattern in _MULTI_WORD_NS:
        if re.search(pattern, sent_lower):
            return "gemischt"

    # --- Schritt 3: Einzelwort-NS-Marker im Satz (Interpunktion entfernt) ---
    for w in raw_words:
        clean = _strip_punct(w).lower()
        if clean in ns_starters:
            return "gemischt"

    return "HS"


def _count_sentence_types(sentences: List[str]) -> Dict[str, int]:
    """Zählt HS, NS und gemischte Sätze."""
    counts = {"HS": 0, "NS": 0, "gemischt": 0}
    for s in sentences:
        stype = _classify_sentence_type(s)
        counts[stype] = counts.get(stype, 0) + 1
    return counts


# ==============================================================================
# HAUPTFUNKTION: EINZELTEXT-ANALYSE
# ==============================================================================

def _strip_metadata_prefix(text: str) -> str:
    """
    Entfernt Metadaten-Praefixe wie **[Buch-Auszug Teil 1]**,
    Autorenangaben, Titelzeilen etc. VOR der Analyse.

    Diese Praefixe verzerren Hotspot-Scores und Versstruktur,
    und erscheinen als Inhaltswörter (z.B. "auszug", "buch").

    Muster die entfernt werden:
    - **[Buch-Auszug ...]**  (beliebiger Inhalt in eckigen Klammern)
    - Autor+Titel-Zeilen (z.B. „Heinrich Heine — „Atlas" (1827)")
    - (Publicado in / Veröffentlicht in / Опубликовано в ...)
    """
    import re

    # 1. **[Buch-Auszug ...]** Muster entfernen
    cleaned = re.sub(r'\*\*\[.*?\]\*\*\s*', '', text)

    # 2. Zeilen mit "Auszug" / "auszug" alleine entfernen
    cleaned = re.sub(r'(?m)^.*[Aa]uszug.*$', '', cleaned)

    # 3. Autor+Titel-Zeilen entfernen (v58.2: Lyrik-Relevanz)
    # Muster: Name — „Titel" (Jahr) oder Name — "Titel" (Jahr)
    # Auch: Name — „Titel" / „Übersetzung" (Jahr)
    cleaned = re.sub(
        r'(?m)^.{3,60}[—–-]\s*[«"„].*?[»""].*?\(\d{4}\)\s*$',
        '', cleaned
    )
    # Ohne Jahreszahl: Name — „Titel"
    cleaned = re.sub(
        r'(?m)^.{3,60}[—–-]\s*[«"„].*?[»""]\s*$',
        '', cleaned
    )

    # 4. Publikationsangaben entfernen
    cleaned = re.sub(r'(?m)^\(Опубликовано.*?\)\s*$', '', cleaned)
    cleaned = re.sub(r'(?m)^\(Veröffentlicht.*?\)\s*$', '', cleaned)
    cleaned = re.sub(r'(?m)^\(Published.*?\)\s*$', '', cleaned)

    # 5. Mehrfache Leerzeilen zusammenfassen
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    # 6. QUELLE-N:-Präfixe entfernen (Lab-Pipeline-Metadaten)
    cleaned = re.sub(r'(?m)^QUELLE\s+\d+:\s*.*$', '', cleaned)

    # 7. Generische Chunk-Header entfernen (v59.4)
    cleaned = re.sub(r'(?m)^\[.{3,300}\]\s*$', '', cleaned)
    
    # 8. Zeilen mit "Sprache:" / "Language:" / "Kapitel:" entfernen
    cleaned = re.sub(r'(?m)^(?:Sprache|Language|Kapitel|Chapter|Source):.*$', '', cleaned)

    return cleaned.strip()

def analyze_text(text: str, source_label: str = "Quelle") -> Dict:
    """
    Etappe 1: SEZIEREN — Deterministische Textanalyse.

    Produziert alle Statistiken, die Etappe 2+3 als Kontext nutzen.
    100% Python, 0% LLM.

    Args:
        text:         Der zu analysierende Text
        source_label: Label für die Quelle (z.B. "QUELLE 1")

    Returns:
        Dict mit allen Analysedaten.
    """
    # ── 0. Validierung ──
    if not text or not text.strip():
        return {"error": "Leerer Text", "source_label": source_label}

    # ── 1. Metadaten-Praefix entfernen (v57.5.2) ──
    text = _strip_metadata_prefix(text)

    # ── 2. Sprach-Dispatch (Patch #7a/#7b, v59.3-fix: Double-Check) ──
    # Steht NACH Metadata-Stripping, damit Präfixe den Schwellenwert nicht drücken
    if _is_greek_text(text):
        return _analyze_greek(text, source_label)
    if _is_hebrew_text(text):
        return _analyze_hebrew(text, source_label)
    
    # ── 2b. Defensiver Double-Check (v59.3-fix) ──
    # Falls _is_greek_text() fehlschlägt (z.B. bilinguale Texte mit hohem
    # Latein-Anteil), die Standard-Tokenisierung aber 0 Wörter findet,
    # UND griechische Zeichen im Text vorhanden sind → erzwingen Greek-Pfad.
    # Dies verhindert "0 Wörter, 1 Sätze" als Endresultat.
    _quick_greek_check = len(_GREEK_UNICODE_RANGES.findall(text))
    if _quick_greek_check > 10 and not _is_greek_text(text):
        # Greek chars vorhanden, aber _is_greek_text() hat sie nicht erkannt
        # (z.B. Metadata-Dilution, bilinguale Texte, Edge-Cases)
        # → Erzwinge Greek-Pfad statt Standard-Analyse mit falscher Segmentierung
        logger.warning(
            f"⚠️ Greek Double-Check aktiviert für {source_label}: "
            f"{_quick_greek_check} griechische Zeichen, aber _is_greek_text()=False. "
            f"Erzwinge _analyze_greek()."
        )
        return _analyze_greek(text, source_label)
    
    # ── 2c. Defensiver Double-Check für Hebräisch (v59.3-fix) ──
    # Symmetrisch zum Greek Double-Check: Falls _is_hebrew_text() fehlschlägt,
    # die Standard-Tokenisierung aber 0 Wörter findet UND hebräische Zeichen
    # vorhanden sind → erzwinge Hebrew-Pfad.
    _quick_hebrew_check = len(_HEBREW_UNICODE_RANGES.findall(text))
    if _quick_hebrew_check > 10 and not _is_hebrew_text(text):
        # Hebrew chars vorhanden, aber _is_hebrew_text() hat sie nicht erkannt
        # (z.B. Metadata-Dilution, bilinguale Texte, Edge-Cases)
        # → Erzwinge Hebrew-Pfad statt Standard-Analyse mit falscher Segmentierung
        logger.warning(
            f"⚠️ Hebrew Double-Check aktiviert für {source_label}: "
            f"{_quick_hebrew_check} hebräische Zeichen, aber _is_hebrew_text()=False. "
            f"Erzwinge _analyze_hebrew()."
        )
        return _analyze_hebrew(text, source_label)

    # ── 3. Sätze segmentieren ──
    sentences = _split_sentences(text)

    # ── 4. Wort-Tokenisierung ──
    words = _tokenize(text)
    content_words, function_words = _classify_words(words)

    # ── 5. Satzstatistiken ──
    sentence_lengths = [len(_tokenize(s)) for s in sentences] if sentences else [0]
    sentence_types = _count_sentence_types(sentences)

    # ── 6. Interpunktions-Verteilung ──
    punctuation = {
        "Komma": text.count(","),
        "Punkt": text.count("."),
        "Ausrufezeichen": text.count("!"),
        "Fragezeichen": text.count("?"),
        "Doppelpunkt": text.count(":"),
        "Strichpunkt": text.count(";"),
        "Gedankenstrich": text.count("–") + text.count("—") + text.count("-"),
        "Auslassungspunkte": text.count("…") + text.count("..."),
    }

    # ── 7. Top-Inhaltswörter und Funktionswörter ──
    content_freq = Counter(content_words)
    function_freq = Counter(function_words)

    # ── 8. N-Gramme ──
    bigrams = _extract_ngrams(words, n=2, min_freq=2)
    trigrams = _extract_ngrams(words, n=3, min_freq=2)

    # ── 9. Absatzstruktur ──
    paragraph_stats = _analyze_paragraphs(text)

    # ── 10. Hotspot-Sätze ──
    hotspots = _find_hotspot_sentences(sentences, top_k=5)

    # ── 10b. Komposita / Wortschöpfungen (v59.6) ──
    # C5-FIX (v59.8): language="auto" statt "de" — damit werden auch
    # russische (B14) und ggf. andere Sprachen erkannt, nicht nur DE.
    composita = _extract_composita(words, sentences, max_items=15, language="auto")

    # ── 11. Lyrik-Proxy (v58.1) ──
    verse_structure = _detect_verse_structure(text)


    # Lyrik-Analytik (v59): Nur wenn LYRIK-SIGNAL ≥ "mittel"
    verse_detail = _get_empty_verse_detail()  # v59.3-fix (Kimi B1): Null-Struktur statt {}
    if verse_structure.get("signal_strength") in ("stark", "mittel"):
        # B13-FIX: Versnummern filtern bevor Lyrik-Analytik läuft
        text_clean = _filter_verse_lines(text)
        rhyme_result = _detect_rhyme_scheme(text_clean)  # v59.3: vorher berechnen, für Vokal-Echo-Filter
        verse_detail = {
            "stanzas": _detect_stanzas(text_clean),
            "rhyme": rhyme_result,
            "sound_patterns": _detect_sound_patterns(text_clean),
            "enjambement": _detect_enjambement(text_clean),
            "rhythm": _analyze_verse_rhythm(text_clean),
            "vowel_skeletons": _extract_vowel_skeleton(text_clean),  # v59: Vokalgerüst
            "vowel_echoes": _detect_vowel_echoes(text_clean, rhyme_type=rhyme_result.get("rhyme_type", "Kein Reim")),  # v59.3: rhyme_type übergeben
        }

    # 9. Morphologische Komplexität (gesamt)
    morph_complexity = _morphological_complexity(words)

    # 10. TTR / STTR
    ttr = _type_token_ratio(words)
    sttr = _standardized_ttr(words, segment_size=100)

    result = {
        "source_label": source_label,
        "text_length_chars": len(text),
        "text_length_words": len(words),
        "sentence_count": len(sentences),
        "sentence_stats": {
            "avg_length": round(sum(sentence_lengths) / len(sentence_lengths), 1) if sentence_lengths else 0,
            "median_length": round(sorted(sentence_lengths)[len(sentence_lengths) // 2], 1) if sentence_lengths else 0,
            "max_length": max(sentence_lengths) if sentence_lengths else 0,
            "min_length": min(sentence_lengths) if sentence_lengths else 0,
        },
        "sentence_types": sentence_types,
        "type_token_ratio": round(ttr, 3),
        "sttr": round(sttr, 3),
        "morphological_complexity": morph_complexity,
        "punctuation": punctuation,
        "top_content_words": content_freq.most_common(10),
        "top_function_words": function_freq.most_common(5),
        "bigrams": bigrams[:5],
        "trigrams": trigrams[:5],
        "paragraph_stats": paragraph_stats,
        "hotspot_sentences": hotspots,
        "composita": composita,               # v59.6: Komposita / Wortschöpfungen
        "verse_structure": verse_structure,   # v58.1: Lyrik-Proxy
        "verse_detail": verse_detail,         # v58.2: Lyrik-Analytik (leer bei Prosa)
    }

    logger.info(
        f"📊 Etappe 1 abgeschlossen: {source_label} — "
        f"{len(words)} Wörter, {len(sentences)} Sätze, "
        f"TTR={ttr:.3f}, Morph={morph_complexity}"
    )

    return result


# ==============================================================================
# VERGLEICHENDE ANALYSE
# ==============================================================================

def analyze_texts_comparative(
    source_texts: Dict[str, str],
) -> Dict:
    """
    Vergleichende Analyse mehrerer Quellen.

    Erzeugt:
    1. Individuelle Statistiken pro Quelle
    2. Vergleichstabelle (für Etappe 2+3 Kontext)
    3. Gesamtkontext

    Args:
        source_texts: Dict {source_label: text_content}

    Returns:
        Dict mit 'individual', 'comparison_table', 'summary'.
    """
    individual = {}
    for label, text in source_texts.items():
        individual[label] = analyze_text(text, source_label=label)

    # Vergleichstabelle aufbauen
    comparison_rows = []
    for label, stats in individual.items():
        if "error" in stats:
            # Claude-Audit-Fix: Warnung statt stillschweigendem Überspringen.
            # Vorher: continue ohne Log → Fehler unsichtbar.
            logger.warning(
                f"⚠️ Etappe 1 übersprungen: {label} — "
                f"Fehler: {stats.get('error', 'unbekannt')}"
            )
            continue
        row = {
            "Quelle": label,
            "Wörter": stats["text_length_words"],
            "Sätze": stats["sentence_count"],
            "Ø Satzlänge": stats["sentence_stats"]["avg_length"],
            "Max Satzlänge": stats["sentence_stats"]["max_length"],
            "HS": stats["sentence_types"].get("HS", 0),
            "NS": stats["sentence_types"].get("NS", 0),
            "Gemischt": stats["sentence_types"].get("gemischt", 0),
            "TTR": stats["type_token_ratio"],
            "STTR": stats["sttr"],
            "Morph.Kompl.": stats["morphological_complexity"],
            "Kommas": stats["punctuation"].get("Komma", 0),
            "Absätze": stats["paragraph_stats"]["count"],
            # ── Lyrik-Spalten (v59 Klang-Durchgriff) ──
            "Lyrik": stats.get("verse_structure", {}).get("signal_strength", "—"),
            "Strophen": stats.get("verse_detail", {}).get("stanzas", {}).get("stanza_count", 0),
            "Reim": stats.get("verse_detail", {}).get("rhyme", {}).get("rhyme_type", "—"),
            "Ø Silben": stats.get("verse_detail", {}).get("rhythm", {}).get("avg_syllables", 0),
            "Enjamb.": stats.get("verse_detail", {}).get("enjambement", {}).get("count", 0),
            "Komposita": len(stats.get("composita", [])),
        }
        comparison_rows.append(row)

    # B11-FIX (v59.7): Sortieren nach QuelLabel statt nach Wortzahl.
    # Vorher: Sortierung nach Wortzahl → Q3, Q2, Q4, Q1 (verwirrend).
    # Jetzt: Numerische Extraktion aus Label (QUELLE 1, QUELLE 2 etc.)
    # → konsistente Reihenfolge Q1, Q2, Q3, Q4 über alle Läufe.
    def _extract_quelle_nr(row):
        """Extrahiere Nummer aus QuelLabel für Sortierung."""
        label = row.get("Quelle", "")
        m = re.search(r'(\d+)', label)
        return int(m.group(1)) if m else 999
    comparison_rows.sort(key=_extract_quelle_nr)

    # Zusammenfassung
    valid_sources = [s for s in individual.values() if "error" not in s]
    summary = {
        "source_count": len(valid_sources),
        "total_words": sum(s["text_length_words"] for s in valid_sources),
        "total_sentences": sum(s["sentence_count"] for s in valid_sources),
    }

    result = {
        "individual": individual,
        "comparison_table": comparison_rows,
        "summary": summary,
    }

    logger.info(
        f"📊 Vergleichende Analyse: {len(valid_sources)} Quellen, "
        f"{summary['total_words']} Wörter gesamt"
    )

    return result


# ==============================================================================
# FORMATIERUNG: ETAPPE 1 ERGEBNISSE ALS TEXT (für LLM-Kontext)
# ==============================================================================

def format_stats_for_llm(stats: Dict) -> str:
    """
    Formatiert Etappe-1-Ergebnisse als lesbaren Text für den LLM-Kontext.
    Etappe 2+3 bekommt diesen Text als Faktenbasis.

    Args:
        stats: Ergebnis von analyze_text()

    Returns:
        Formatierter String mit allen Statistiken.
    """
    if "error" in stats:
        return f"FEHLER: {stats['error']}"

    lines = []
    lines.append(f"=== STATISTIKEN: {stats['source_label']} ===")
    lines.append("")

    # Grundzahlen
    lines.append(f"Textlänge: {stats['text_length_words']} Wörter, {stats['text_length_chars']} Zeichen")
    lines.append(f"Sätze: {stats['sentence_count']}")
    lines.append("")

    # Satzstatistiken
    ss = stats["sentence_stats"]
    lines.append("Satzlängen:")
    lines.append(f"  Ø {ss.get('avg_length', 0)} Wörter | Median {ss.get('median_length', 0)} | Max {ss.get('max_length', 0)} | Min {ss.get('min_length', 0)}")
    st = stats["sentence_types"]
    lines.append(f"  HS: {st.get('HS', 0)} | NS: {st.get('NS', 0)} | gemischt: {st.get('gemischt', 0)}")
    lines.append("")

    # TTR
    lines.append(f"Type-Token-Ratio: {stats['type_token_ratio']} (STTR: {stats['sttr']})")
    lines.append(f"Morphologische Komplexität: {stats['morphological_complexity']}")

    # Lyrik-Proxy (v58.1) + Lyrik-Analytik (v58.2)
    vs = stats.get("verse_structure", {})
    vd = stats.get("verse_detail", {})
    if vs.get("is_likely_verse"):
        lines.append(
            f"LYRIK-SIGNAL: {vs.get('signal_strength', '?')} "
            f"(\u00d8 {vs.get('avg_words_per_line', 0)} W\u00f6rter/Zeile, "
            f"\u03c3 {vs.get('stdev_words_per_line', 0)})"
        )
        lines.append("")

        # ── VERSSTRUKTUR (v58.2) ──
        if vd:
            stanzas = vd.get("stanzas", {})
            rhyme = vd.get("rhyme", {})
            sound = vd.get("sound_patterns", {})
            enjamb = vd.get("enjambement", {})
            rhythm = vd.get("rhythm", {})

            lines.append("── VERSSTRUKTUR ──")

            # Strophen
            if stanzas.get("stanza_count", 0) > 0:
                lines.append(
                    f"Strophen: {stanzas['stanza_count']} "
                    f"({stanzas.get('stanza_pattern', '')})"
                )

            # Rhythmus
            if rhythm.get("avg_syllables", 0) > 0:
                lines.append(
                    f"Rhythmus: {rhythm.get('pattern_description', '')} "
                    f"(\u00d8 {rhythm['avg_syllables']} Silben, "
                    f"\u03c3 {rhythm['stdev_syllables']})"
                )
                # Silben pro Vers (kompakt)
                syl = rhythm.get("syllables_per_line", [])
                if syl:
                    lines.append(f"  Silben pro Vers: {syl}")

            # Reimschema
            if rhyme.get("scheme_notation"):
                lines.append(
                    f"Reimschema: {rhyme['scheme_notation']} "
                    f"({rhyme.get('rhyme_type', '')})"
                )
                # Reimpaare
                for pair in rhyme.get("rhyme_pairs", [])[:8]:
                    lines.append(
                        f"  {pair['label']}: {pair['word_a']} / {pair['word_b']} "
                        f"(V.{pair['line_a']}+V.{pair['line_b']})"
                    )

            # Enjambements
            enj_count = enjamb.get("count", 0)
            if enj_count > 0:
                lines.append(
                    f"Enjambements: {enj_count} "
                    f"({enjamb.get('percentage', 0)}% der Zeilen\u00fcberg\u00e4nge)"
                )
                for ej in enjamb.get("enjambements", [])[:5]:
                    lines.append(
                        f"  V.{ej['from_line']}\u2192V.{ej['to_line']}: "
                        f"...{ej['fragment_a']} | {ej['fragment_b']}..."
                    )

            # v59.2: Vokalgerüste aus der Ausgabe entfernt (unlesbar für LLM)
            # Die Rohdaten bleiben im verse_detail Dict für eventuelle spätere Nutzung

            # Vokal-Echos (v59.3: mit Trivial- + Reim-Filter)
            vechoes_data = vd.get("vowel_echoes", {})
            vechoes = vechoes_data.get("echoes", []) if isinstance(vechoes_data, dict) else vechoes_data if isinstance(vechoes_data, list) else []
            trivial_vowel = vechoes_data.get("trivial_vowel") if isinstance(vechoes_data, dict) else None
            trivial_ratio = vechoes_data.get("trivial_ratio", 0.0) if isinstance(vechoes_data, dict) else 0.0
            rhyme_filtered = vechoes_data.get("rhyme_filtered", False) if isinstance(vechoes_data, dict) else False
            rhyme_filtered_count = vechoes_data.get("rhyme_filtered_count", 0) if isinstance(vechoes_data, dict) else 0

            # Trivial-Hinweis: Wenn ein Vokal >50% der Endungen dominiert
            if trivial_vowel:
                lines.append(
                    f"Vokal-Hinweis: Endvokal '{trivial_vowel}' dominiert "
                    f"({trivial_ratio:.0%} der Zeilenenden) — Echos daraus sind trivial und werden nicht gezeigt."
                )

            # v59.3: Hinweis bei reim-bedingt gefilterten Echos
            if rhyme_filtered:
                lines.append(
                    f"Vokal-Echos: {rhyme_filtered_count} Echos mit Abstand ≤ 2 wurden unterdrückt "
                    f"(strukturbedingt durch Reimschema {rhyme.get('rhyme_type', '')})."
                )

            if vechoes:
                lines.append("Vokal-Echos (nicht-triviale Endvokal-Übereinstimmungen):")
                for ve in vechoes[:8]:
                    lines.append(
                        f"  V.{ve['line_a']}→V.{ve['line_b']}: "
                        f"Endvokal '{ve['end_vowel']}' (Abstand {ve['distance']})"
                    )
            elif not trivial_vowel and not rhyme_filtered:
                lines.append("Vokal-Echos: keine signifikanten Übereinstimmungen gefunden.")
            lines.append("")

            # Klangfiguren
            allit = sound.get("alliterations", [])
            asson = sound.get("assonances", [])
            innen = sound.get("internal_rhymes", [])
            if allit or asson or innen:
                lines.append("Klangfiguren:")
                for a in allit[:8]:
                    if a.get("cross_verse"):
                        # v59.3: Versübergreifende Alliteration
                        lines.append(
                            f"  Alliteration ({a['consonant'].upper()}): "
                            f"{', '.join(a['words'][:4])}  [V.{a['line']}–V.{a['line_end']}, versübergreifend]"
                        )
                    else:
                        lines.append(
                            f"  Alliteration ({a['consonant'].upper()}): "
                            f"{', '.join(a['words'][:4])}  [V.{a['line']}]"
                        )
                for a in asson[:5]:
                    lines.append(
                        f"  Assonanz ({a['vowel_pattern']}): "
                        f"{a['word_a']} / {a['word_b']}  [V.{a['line']}]"
                    )
                for ir in innen[:3]:
                    lines.append(
                        f"  Binnenreim: {ir['word_a']} / {ir['word_b']}  [V.{ir['line']}]"
                    )

            lines.append("")
    lines.append("")

    # Interpunktion
    lines.append("Interpunktion:")
    for punct, count in stats["punctuation"].items():
        if count > 0:
            lines.append(f"  {punct}: {count}")
    lines.append("")

    # Top-Wörter
    if stats["top_content_words"]:
        lines.append("Häufigste Inhaltswörter:")
        for word, count in stats["top_content_words"][:5]:
            lines.append(f"  {word}: {count}×")
        lines.append("")

    # N-Gramme
    if stats["bigrams"]:
        lines.append("Häufigste Bigramme:")
        for gram, count in stats["bigrams"][:5]:
            lines.append(f"  {gram}: {count}×")
        lines.append("")

    if stats["trigrams"]:
        lines.append("Häufigste Trigramme:")
        for gram, count in stats["trigrams"][:3]:
            lines.append(f"  {gram}: {count}×")
        lines.append("")

    # Absatzstruktur
    ps = stats["paragraph_stats"]
    lines.append(f"Absätze: {ps.get('count', 0)} (Ø {ps.get('avg_chars', 0)} Zeichen, σ {ps.get('length_variance', 0)})")
    lines.append("")

    # Hotspot-Sätze
    if stats["hotspot_sentences"]:
        lines.append("HOTSPOT-SÄTZE (auffälligste Sätze):")
        for i, hs in enumerate(stats["hotspot_sentences"], 1):
            reasons = ", ".join(hs.get("reasons", ["—"]))
            sent_preview = hs["sentence"][:200] + ("..." if len(hs["sentence"]) > 200 else "")
            lines.append(f"  [{i}] Score {hs['score']:.2f} ({reasons})")
            lines.append(f"      „{sent_preview}\"")
        lines.append("")

    # Komposita / Wortschöpfungen (v59.6)
    composita = stats.get("composita", [])
    if composita:
        lines.append("KOMPOSITA / WORTSCHÖPFUNGEN (zusammengesetzte Wörter):")
        for i, comp in enumerate(composita, 1):
            comp_typ = comp.get("typ", comp.get("type", "—"))
            comp_wort = comp.get("wort", comp.get("word", "—"))
            comp_ctx = comp.get("kontext", comp.get("context", ""))
            comp_bestandteile = comp.get("bestandteile", [])
            comp_haeuf = comp.get("haeufigkeit", 1)
            comp_laenge = comp.get("laenge", len(comp_wort))
            # Zeile 1: Wort — Typ (Länge N Zchn, Häufigkeit M)
            lines.append(f"  [{i}] {comp_wort} — {comp_typ} ({comp_laenge} Zchn, Häuf. {comp_haeuf})")
            # Zeile 2: Bestandteile (falls vorhanden)
            if comp_bestandteile:
                lines.append(f"      Bestandteile: {' + '.join(comp_bestandteile)}")
            # Zeile 3: Kontext (max 120 Zchn)
            if comp_ctx:
                ctx_preview = comp_ctx[:117] + ("..." if len(comp_ctx) > 120 else "")
                lines.append(f"      Kontext: „{ctx_preview}\"")
        lines.append("")
    else:
        lines.append("KOMPOSITA / WORTSCHÖPFUNGEN:")
        lines.append("  Keine auffälligen Komposita gefunden.")
        lines.append("")

    return "\n".join(lines)


def format_comparison_table_for_llm(comparison_rows: List[Dict]) -> str:
    """
    Formatiert die Vergleichstabelle als lesbaren Text für den LLM-Kontext.

    Args:
        comparison_rows: Liste von Zeilen-Dicts aus analyze_texts_comparative()

    Returns:
        Formatierter String mit Vergleichstabelle.
    """
    if not comparison_rows:
        return "Keine Vergleichsdaten verfügbar."

    lines = []
    lines.append("=== VERGLEICHSTABELLE ===")
    lines.append("")

    # Header (v59 Klang-Durchgriff: Lyrik-Spalten ergänzt)
    headers = ["Quelle", "Wörter", "Sätze", "Ø Satzl.", "Max", "HS", "NS", "Gem.", "TTR", "Morph", "Kommas", "Lyrik", "Stroph.", "Reim", "Ø Silb.", "Enjamb.", "Komposita"]
    lines.append(" | ".join(f"{h:>10}" for h in headers))
    lines.append("-" * (len(headers) * 12))

    # Zeilen
    for row in comparison_rows:
        def _fmt(val, fmt=None):
            """Formatiere einen Wert für die Tabelle."""
            if val == "—" or val is None:
                return "—"
            if fmt:
                return fmt.format(val)
            s = str(val)
            if len(s) > 18:
                s = s[:16] + ".."
            return s

        values = [
            _fmt(row.get("Quelle", "—")),
            _fmt(row.get("Wörter", "—")),
            _fmt(row.get("Sätze", "—")),
            _fmt(row.get("Ø Satzlänge", "—")),
            _fmt(row.get("Max Satzlänge", "—")),
            _fmt(row.get("HS", "—")),
            _fmt(row.get("NS", "—")),
            _fmt(row.get("Gemischt", "—")),
            _fmt(row.get("TTR", 0), "{:.3f}"),
            _fmt(row.get("Morph.Kompl.", 0), "{:.1f}"),
            _fmt(row.get("Kommas", "—")),
            # ── Lyrik-Spalten (v59) ──
            _fmt(row.get("Lyrik", "—")),
            _fmt(row.get("Strophen", "—")),
            _fmt(row.get("Reim", "—")),
            _fmt(row.get("Ø Silben", "—")),
            _fmt(row.get("Enjamb.", "—")),
            _fmt(row.get("Komposita", "—")),
        ]
        lines.append(" | ".join(f"{v:>10}" for v in values))

    lines.append("")
    return "\n".join(lines)
