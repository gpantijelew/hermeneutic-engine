# modules/text_analyzer.py — v59.3: Etappe 1 SEZIEREN + Klang-Schärfung (Binnenreim-Fix + Vokal-Echo-Rauschfilter + versübergreifende Alliteration)
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
    """
    # Unicode-Wort-Regex: Buchstaben aller Schriften (Latin, Cyrillic, etc.)
    # \w mit re.UNICODE schliesst Zahlen und _ ein, deshalb [\p{L}]+
    # Python re unterstuetzt kein \p{L}, also manuell:
    # Latin + Kyrillisch + allgemeine Unicode-Buchstaben
    words = re.findall(
        r'[a-zA-ZäöüÄÖÜßáàéèíìóòúù'
        r'\u0400-\u04FF'   # Kyrillisch (Russisch, Ukrainisch, etc.)
        r'\u0500-\u052F'   # Kyrillisch Ergaenzung
        r']+',
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
    muss es aber nicht. Die Modus-Erkennung entscheidet.

    Args:
        text: Der zu analysierende Text.

    Returns:
        Dict mit: is_likely_verse, avg_words_per_line, stdev_words_per_line,
        line_count, signal_strength ("stark"/"mittel"/"kein")
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
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

    Args:
        text: Der zu analysierende Text.

    Returns:
        Dict mit: rhyme_pairs, scheme_labels, scheme_notation,
        rhyme_type ("Kreuzreim"/"Paarreim"/"Umarmender Reim"/"Gemischt"/"Kein Reim")
    """
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
    return {
        "echoes": echoes[:12],
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

    return {
        "alliterations": alliterations[:20],
        "assonances": assonances[:15],
        "internal_rhymes": internal_rhymes[:10],
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
    if not text or not text.strip():
        return {"error": "Leerer Text", "source_label": source_label}

    # 0. Metadaten-Praefix entfernen (v57.5.2)
    text = _strip_metadata_prefix(text)

    # 1. Sätze segmentieren
    sentences = _split_sentences(text)

    # 2. Wort-Tokenisierung
    words = _tokenize(text)
    content_words, function_words = _classify_words(words)

    # 3. Satzstatistiken
    sentence_lengths = [len(_tokenize(s)) for s in sentences] if sentences else [0]
    sentence_types = _count_sentence_types(sentences)

    # 4. Interpunktions-Verteilung
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

    # 5. Top-Inhaltswörter und Funktionswörter
    content_freq = Counter(content_words)
    function_freq = Counter(function_words)

    # 6. N-Gramme
    bigrams = _extract_ngrams(words, n=2, min_freq=2)
    trigrams = _extract_ngrams(words, n=3, min_freq=2)

    # 7. Absatzstruktur
    paragraph_stats = _analyze_paragraphs(text)

    # 8. Hotspot-Sätze
    hotspots = _find_hotspot_sentences(sentences, top_k=5)

    # Lyrik-Proxy (v58.1)
    verse_structure = _detect_verse_structure(text)

    # Lyrik-Analytik (v59): Nur wenn LYRIK-SIGNAL ≥ "mittel"
    verse_detail = {}
    if verse_structure.get("signal_strength") in ("stark", "mittel"):
        rhyme_result = _detect_rhyme_scheme(text)  # v59.3: vorher berechnen, für Vokal-Echo-Filter
        verse_detail = {
            "stanzas": _detect_stanzas(text),
            "rhyme": rhyme_result,
            "sound_patterns": _detect_sound_patterns(text),
            "enjambement": _detect_enjambement(text),
            "rhythm": _analyze_verse_rhythm(text),
            "vowel_skeletons": _extract_vowel_skeleton(text),  # v59: Vokalgerüst
            "vowel_echoes": _detect_vowel_echoes(text, rhyme_type=rhyme_result.get("rhyme_type", "Kein Reim")),  # v59.3: rhyme_type übergeben
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
            "Strophen": stats.get("verse_detail", {}).get("stanzas", {}).get("stanza_count", "—"),
            "Reim": stats.get("verse_detail", {}).get("rhyme", {}).get("rhyme_type", "—"),
            "Ø Silben": stats.get("verse_detail", {}).get("rhythm", {}).get("avg_syllables", "—"),
            "Enjamb.": stats.get("verse_detail", {}).get("enjambement", {}).get("count", "—"),
        }
        comparison_rows.append(row)

    # Sortieren nach Wortanzahl (absteigend)
    comparison_rows.sort(key=lambda r: r["Wörter"], reverse=True)

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
    lines.append(f"  Ø {ss['avg_length']} Wörter | Median {ss['median_length']} | Max {ss['max_length']} | Min {ss['min_length']}")
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
    lines.append(f"Absätze: {ps['count']} (Ø {ps['avg_chars']} Zeichen, σ {ps['length_variance']})")
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
    headers = ["Quelle", "Wörter", "Sätze", "Ø Satzl.", "Max", "HS", "NS", "Gem.", "TTR", "Morph", "Kommas", "Lyrik", "Stroph.", "Reim", "Ø Silb.", "Enjamb."]
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
        ]
        lines.append(" | ".join(f"{v:>10}" for v in values))

    lines.append("")
    return "\n".join(lines)
