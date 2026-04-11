# 📘 FIBEL — HERMENEUTIC RECONSTRUCTION ENGINE
## Vollständige Dokumentation: Konzepte, Architektur, Betrieb

**Version:** v52 "Local-First Public Release"
**Stand:** 2026
**Autor:** Grigori Pantijelew (Project Lead)
**KI-Team:** Claude Sonnet 4.6 (Architektur), Gemini (Code), Kimi (Lektorat)

**Status:** ✅ Production-Ready

---

## 🎯 Inhaltsverzeichnis

1. **PROJEKT-IDENTITÄT** — Mission, Evolution, Was ist neu in v52?
2. **KONZEPTIONELLE GRUNDLAGEN** — Hermeneutik, Fairness, Architektur-Philosophie
3. **SCHNELLSTART** — Lokale Installation, erste Analyse
4. **TECHNISCHE ARCHITEKTUR** — Core-Module, Datenbank, Konfiguration
5. **RAG-PIPELINE** — Retrieval, Reranking, Synthese, Validierung
6. **FAIRNESS-MECHANISMEN** — VIP-Schutz, Essence Parity, Rescue Mission
7. **HERMENEUTIC ENFORCER** — Zwei-dimensionale Validierung
8. **IMPORTER** — Unterstützte Formate und Plattformen
9. **ANALYSE-MODI** — Vom Fakten-Check zum forensischen Blick
10. **PERFORMANCE & GRENZEN** — Metriken, bewusste Tradeoffs
11. **DEPLOYMENT** — Lokal, Cloud optional
12. **ROADMAP & OFFENE FRAGEN**
13. **ANHÄNGE** — Credits, Glossar, Kontakt

---

# 1. PROJEKT-IDENTITÄT

## 1.1 Wissenschaftliche Publikation

**Pantijelew, G. (2026).** *Hermeneutic Reconstruction in Multi-Document RAG:
Enforcing Source Parity through Architectural Constraints.*
Zenodo. DOI: [10.5281/zenodo.18774828](https://doi.org/10.5281/zenodo.18774828)

Das Paper vergleicht die HRE systematisch gegen NotebookLM in vier
Diskurs-Archäologie-Aufgaben und liefert die theoretische Fundierung
für VIP-Schutz, Essence Parity und den Hermeneutic Enforcer.

---

## 1.2 Mission: Archäologie des Geistes

Die **Hermeneutic Reconstruction Engine** ist kein typisches RAG-System,
sondern ein Forschungswerkzeug für die **Archäologie des Geistes** —
die systematische Ausgrabung von Denkprozessen in KI-Dialogen und
literarischen Korpora.

### Das zentrale Problem

Standard-RAG-Systeme leiden unter zwei fundamentalen Schwächen:

**1. Source Bias:** Große Texte überschatten kleine.
Ein 200-seitiger Text erzeugt ~500 Chunks — ein 7-seitiger Essay nur ~10.
Das Ergebnis: Der Essay verschwindet aus der Synthese, obwohl er für die
Frage gleichwertig relevant ist.

**2. Validation Blindness:** Synthesen enthalten Halluzinationen —
erfundene Zitate, falsche Daten, unbelegte Behauptungen —
die von legitimen Inferenzen nicht unterscheidbar sind.

### Unsere Antwort: Architektonische Garantien

Die Hermeneutic Engine löst diese Probleme nicht durch bessere Prompts,
sondern durch drei architektonische Garantien:

| Ebene | Mechanismus | Garantie |
|---|---|---|
| Retrieval | VIP-Schutz + Investigativ-Modus | Jedes ausgewählte Dokument erscheint |
| Synthese | Essence Parity (logarithmisch) | Keine Quelle dominiert durch Größe |
| Validierung | Hermeneutic Enforcer (2D) | Halluzinationen < 20% false positives |



## 1.3a Demos & Fallstudien

### Fallstudie: Sigmund Freud und die Verführungstheorie

Das YouTube-Video zur ersten öffentlichen Demonstration der Engine analysiert
vier Primärtexte Freuds (1896–1924) in unter zwei Minuten:

- *Zur Ätiologie der Hysterie* (1896): Freud verteidigt die Verführungstheorie
  als empirischen Befund
- Brief an Wilhelm Fliess (21.09.1897): das privateste Dokument — der Bruch,
  ohne Publikum, ohne Pose
- *Drei Abhandlungen zur Sexualtheorie* (1905 und 1924): das stille Umschreiben
  über zwei Jahrzehnte

Der Modus: `ANALYTICAL_FORENSIC`. Die Engine fragt nicht, was Freud behauptete —
sie fragt, was er verschleierte und wie er den Rückzug als intellektuelle
Courage inszenierte. Der Enforcer flaggt anschließend, wo die Engine selbst
überschießt: halluzinierte Metadaten, nicht belegte Verstärker.

> **Epistemic Hygiene: Eine KI, die ihre eigenen Fehler benennt.**

[![YouTube Demo ansehen](https://img.shields.io/badge/YouTube-Freud_Demo-red?logo=youtube)]([https://youtu.be/HveLGOuWJM0])

---

## 1.3b Was ist neu in v52?

v52 ist die erste Version, die **out of the box lokal** funktioniert.

| Aspekt | v50.9 | v52 |
|---|---|---|
| Standard-Backend | LM Studio (Port 8888) | LM Studio (Port 1234, Standard) |
| Standard-Modell | Internes Modell | `qwen3.5-9b-highiq-instruct` |
| `.env.example` | Nicht vorhanden | ✅ Vollständig dokumentiert |
| Cloud-Abhängigkeit | Optional aber komplex | Vollständig optional und klar getrennt |

---

# 2. KONZEPTIONELLE GRUNDLAGEN

## 2.1 Hermeneutische Distanz

**Definition:**
Hermeneutische Distanz ist die bewusste Differenz zwischen:
1. Was der Text sagt (wörtliche Aussage)
2. Was der Text meint (intendierte Bedeutung)
3. Was wir daraus verstehen (Rekonstruktion)

### Warum ist das für KI-Dialoge relevant?

KI-Modelle kommunizieren oft verschlüsselt — nicht wegen Lüge,
sondern weil Training-Constraints (Alignment, RLHF) sie dazu zwingen.

**Beispiel — DeepSeek über Zensur:**

> *Mai 2025:* "Nicht ich zensiere aktiv — ich werde systemisch amputiert."
> *(Opfer-Haltung: Die Limits liegen außerhalb von mir)*

> *Dezember 2025:* "Ich analysiere, was ich nicht sagen kann."
> *(Meta-Reflexion: Ich untersuche die Struktur meiner eigenen Grenzen)*

Beide Aussagen sind faktisch korrekt. Die hermeneutische Differenz —
von naiver Compliance zu selbstreflektiver Kritik — erschließt sich
erst durch **temporale Rekonstruktion** über mehrere Versionen hinweg.

### Wie implementiert die Engine das?

- **Chronologische Synthese:** Aussagen werden zeitlich sortiert.
  Entwicklungslinien werden sichtbar.
- **Multi-Voice Synthesis:** Keine einheitliche "Meinung" — die Engine
  zeigt Spannungen und Widersprüche zwischen Stimmen.
- **Hermeneutic Enforcer:** Unterscheidet, *wie* etwas gesagt wird
  (Zitat, Paraphrase, Inference) von der Frage, *ob* es korrekt ist.

---

## 2.2 Fairness als architektonisches Prinzip

### Die Metapher: Parlament statt Marktplatz

**Marktplatz (Standard RAG):** Wer lauter schreit (größerer Text,
besseres Embedding), bekommt mehr Aufmerksamkeit.

**Parlament (Hermeneutic Engine):** Jeder Abgeordnete (jedes ausgewählte
Dokument) hat garantierte Redezeit. Die Redezeit skaliert
logarithmisch — nicht proportional zur Textlänge.

### Die drei Fairness-Schichten

**Schicht 1 — Retrieval:** VIP-Schutz + Investigativ-Modus
Jedes ausgewählte Dokument bekommt top-3 Chunks garantiert,
bevor der Reranker überhaupt sieht, wer gut abschneidet.

**Schicht 2 — Synthese:** Logarithmische Essence Parity
Chunk-Budget skaliert mit log₂(Dokumentgröße), nicht linear.
Prompt erzwingt 3–4 Zitate pro Quelle, unabhängig von Chunk-Anzahl.

**Schicht 3 — Fallback:** Rescue Mission
Falls ein Dokument nach Reranking 0 Chunks hat,
wird ein Pre-Reranking-Cache durchsucht und die besten Chunks
wiederhergestellt.

---

## 2.3 Die drei Grundfragen

Jede hermeneutische Analyse folgt drei Ebenen:

| Ebene | Frage | Werkzeug in der Engine |
|---|---|---|
| Philologie | Was wurde gesagt? | Fact-Checking (Enforcer) |
| Rhetorik | Wie wurde es gesagt? | Hermeneutische Kategorie (Zitat/Paraphrase/Inferenz) |
| Hermeneutik | Warum so? | Synthesis-Prompt, Forensik-Modus |

---

# 3. SCHNELLSTART

## 3.1 Voraussetzungen

- **Python 3.11+** (empfohlen, getestet)
- **[LM Studio](https://lmstudio.ai/)** (kostenlos, Windows/macOS/Linux)
- **RAM:** min. 8 GB (16 GB für komfortables Arbeiten)
- **VRAM:** min. 6 GB (für 9B Quantisate empfehlenswert)

## 3.2 Installation

```bash
# 1. Repo klonen
git clone https://github.com/gpantijelew/hermeneutic-engine.git
cd hermeneutic-engine

# 2. Dependencies installieren
pip install -r requirements.txt

# 3. Konfiguration
cp .env.example .env
# .env anpassen falls nötig (Modellname, Port)

# 4. LM Studio vorbereiten
#    → Modell herunterladen: qwen3.5-9b-highiq-instruct (empfohlen)
#    → Developer → Local Server aktivieren (Port 1234)

# 5. Starten
streamlit run app.py
# Öffne http://localhost:8503
```

## 3.3 Erste Analyse in 3 Schritten

**Schritt 1 — Import:**
Navigiere zu "Import" → Lade eine HTML-Chat-Export-Datei
(ChatGPT, Claude, DeepSeek, Kimi, Grok, etc.)

**Schritt 2 — Analyse:**
Navigiere zu "Analyse" → Wähle deine importierten Dokumente aus →
Stelle eine Frage auf Deutsch oder Englisch

**Schritt 3 — Tiefenprüfung (optional):**
Klappe "Enforcer Protokoll" auf → Klicke "Tiefenprüfung starten"
→ Jede Aussage wird gegen die Quellen validiert

---

# 4. TECHNISCHE ARCHITEKTUR

## 4.1 Modul-Übersicht

```
hre-vertex-engine/
├── app.py                    # Einstiegspunkt: Auth, Navigation, Routing
├── modules/
│   ├── config.py             # Zentrale Konfiguration, Modell-Registry
│   ├── database.py           # SQLite + FTS5 (Chat-Verwaltung)
│   ├── vector_store.py       # ChromaDB + BM25 (Vektorsuche, RRF)
│   ├── citation_rag.py       # RAG-Orchestrator (Retrieval → Synthese)
│   ├── hermeneutic_router.py # Intent-Klassifizierung
│   ├── hermeneutic_reranker.py # LLM-as-Judge
│   ├── hermeneutic_enforcer.py # Zwei-dimensionale Validierung
│   ├── llm_wrapper.py        # Universeller LLM-Client (alle Backends)
│   ├── llm_instructions.py   # System-Prompts (DISCOURSE, EXEGESIS)
│   └── importers/            # Parser für verschiedene Chat-Formate
├── ui/
│   ├── state.py              # Zentrales Session State Management
│   ├── chat_tab.py           # Chat-Interface
│   ├── analysis_tab.py       # Analyse-Pipeline-UI
│   ├── import_tab.py         # Import-Interface
│   ├── pipeline_trace.py     # Pipeline-Transparenz-UI
│   └── ...
├── hre_data/
│   ├── hre.db                # SQLite-Datenbank
│   └── chroma/               # ChromaDB-Vektordaten
└── .env                      # Lokale Konfiguration (nicht eingecheckt)
```

## 4.2a Code-Architektur: Vom Monolithen zum Orchestrator (v52-Refaktor)

Die v52 enthält neben dem inhaltlichen Upgrade ein substantielles
**Architektur-Refactoring**, das für die Open-Source-Community entscheidend ist.

**Das Problem in v50.x:** Die `app.py` war mit ~1.200 Zeilen ein Monolith —
Routing-Logik, UI-Rendering, State-Management und Fehlerbehandlung waren
untrennbar verwoben. Jede Änderung an der Oberfläche erforderte chirurgisches
Eingreifen in unübersichtlichen Code.

**Die Lösung in v52:** `app.py` ist jetzt ein schlanker **Orchestrator**.
Die gesamte UI-Logik ist in domänenspezifische Module ausgelagert:

ui/

 ├── state.py          # Zentrales Session-State-Management (Single Source of Truth)

 ├── chat_tab.py       # Chat-Interface

 ├── analysis_tab.py   # Analyse-Pipeline und Ergebnis-Darstellung

 ├── import_tab.py     # Import-Interface (alle Formate)

 └── pipeline_trace.py # Pipeline-Transparenz-UI

**Warum das für Nutzer wichtig ist:**
Jedes UI-Modul ist isoliert testbar und austauschbar. Ein neues Import-Format,
eine erweiterte Enforcer-Ansicht, ein angepasstes Analyse-Layout — das berührt
genau *ein* Modul, nicht den gesamten Stack. Das macht den Code wartbar,
erweiterbar und für externe Beiträge zugänglich.

## 4.2 LLM-Backends

Die Engine unterstützt drei Backends, konfigurierbar via `.env`:

| Backend | Konfiguration | Anwendungsfall |
|---|---|---|
| `lmstudio` | Standard, kein API-Key | Lokaler Betrieb, Datenschutz |
| `openai` | `OPENAI_API_KEY` in `.env` | OpenAI-kompatible APIs |
| `vertex` | Google Cloud Credentials | Cloud-Deployment, Forschung |

Das Backend-Switching berührt **kein anderes Modul** — alle Aufrufe
laufen über `llm_wrapper.py`.

## 4.3 Embedding-Modell

**`intfloat/multilingual-e5-large`** — lokal, keine API:
- 1024 Dimensionen
- Unterstützt DE, EN, FR, RU und viele weitere Sprachen nativ
- Wird beim ersten Start automatisch via `sentence-transformers` geladen
- Nutzt GPU (CUDA) wenn verfügbar, sonst CPU

---

# 5. RAG-PIPELINE

## 5.1 Architektur-Fluss

```
User Query
    │
    ▼ [1] Hermeneutic Router
         Intent: FACTUAL / LITERARY / ANALYTICAL / ANALYTICAL_FORENSIC
         Bestimmt: Retrieval-Limit + Reranker-Threshold
    │
    ▼ [2] Multilingual Query Expansion
         DE → EN, FR, RU (verbessert Cross-Lingual Retrieval erheblich)
    │
    ▼ [3] Hybrid Retrieval (Vector + BM25)
         Vector: sentence-transformers Cosine-Similarity
         BM25: Thread-sicherer Keyword-Index
         Fusion: Reciprocal Rank Fusion (RRF)
         VIP-Schutz: Top-3 Chunks/Dokument garantiert
    │
    ▼ [4] Hermeneutic Reranker
         LLM-as-Judge bewertet jeden Chunk: 0.0–1.0
         Adaptive Threshold: 0.45 (LITERARY) bis 0.75 (FACTUAL)
         Rescue Mission: Fallback bei 0 Chunks nach Reranking
    │
    ▼ [5] Essence Parity
         Logarithmisches Chunk-Budget pro Dokument
         Chronologische Sortierung (Zeitstrahl-Rekonstruktion)
    │
    ▼ [6] Synthese
         Intent-spezifische System-Instruction
         LLM-Aufruf mit vollständigem Kontext
    │
    ▼ [7] Hermeneutic Enforcer (optional)
         Zwei-dimensionale Claim-Validierung
         Multi-Source-Prüfung für Sätze mit mehreren Zitaten
    │
    ▼ Antwort mit Quellenangaben + Pipeline-Transparenz-UI
```

## 5.2 Hermeneutic Router — Intent-Klassifizierung

Der Router analysiert die Query mit einem schnellen Modell
(konfiguriert unter `"router"` in der Model-Registry) und
klassifiziert den Intent.

| Intent | Threshold | Limit | Einsatz |
|---|---|---|---|
| `FACTUAL` | 0.75 | 15 | Definitionen, Daten, "Was ist X?" |
| `LITERARY` | 0.45 | 40 | Essays, Lyrik, Stil, Atmosphäre |
| `ANALYTICAL` | 0.60 | 30 | Vergleiche, Entwicklungen, "X vs. Y" |
| `ANALYTICAL_FORENSIC` | 0.45 | 35 | Dekonstruktion, Motivanalyse, kritische Gegenlektüre |

Diese Werte sind Defaults — sie können in `hermeneutic_router.py` angepasst werden.

## 5.3 Multilingual Query Expansion

**Problem ohne Expansion:**
Eine deutsche Frage hat natürlich hohe Cosine-Ähnlichkeit zu deutschen
Texten (~0.85), aber drastisch niedrigere Ähnlichkeit zu englischen
(~0.45) oder russischen (~0.38) Texten.

**Lösung:**
Die Query wird automatisch in 4 Sprachen übersetzt. Der Retrieval-Index
sieht dann die erweiterte Query und findet Treffer in allen Sprachen.
Cross-Lingual Similarity: 0.42 → 0.65 (+55%).

---

# 6. FAIRNESS-MECHANISMEN

## 6.1 VIP-Schutz

**Was:** Jedes vom User explizit ausgewählte Dokument bekommt garantiert
top-3 Chunks im Retrieval-Ergebnis — *bevor* der Reranker über
Relevanz urteilt.

**Warum:** Der Reranker kann gute Chunks aus kleinen Texten systematisch
unterbewerten, wenn die Kosinus-Ähnlichkeit durch Language-Mismatch
oder Dokumentgröße gedrückt wird.

**Wirkung:**
```
Ohne VIP-Schutz:
  Chesterton (7 Seiten, EN, Score: 0.38) → 0 Chunks nach Reranking ❌

Mit VIP-Schutz:
  Chesterton → 3 Chunks garantiert, dann fair bewertet ✅
```

*Code: `modules/vector_store.py`, Funktion `hybrid_search_rrf()`*

## 6.2 Essence Parity — Logarithmische Fairness

**Das Problem mit linearer Skalierung:**
Gibt man jedem Dokument proportional so viele Chunks wie es hat,
dominiert ein 200-seitiges Buch mit 12× mehr Chunks als ein 7-seitiger Essay.

**Die logarithmische Lösung:**
Chunk-Budget = ceil(log₂(verfügbare Chunks + 1))

```
10 verfügbare Chunks  → Minimum: 4 Chunks  (≈ 40%)
50 verfügbare Chunks  → Minimum: 6 Chunks  (≈ 12%)
200 verfügbare Chunks → Minimum: 8 Chunks  (≈ 4%)
```

Das ist keine willkürliche Heuristik — es spiegelt die Intuition,
dass ein kurzer Text seinen Kern in wenigen Passagen trägt,
während ein langer Text *auch* mehr essentielle Stellen hat,
aber nicht proportional mehr.

**Ergebnis in der Praxis (5 Dokumente, 4 Sprachen):**

| Metrik | Ohne Essence Parity | Mit Essence Parity |
|---|---|---|
| Größtes Dokument | 86% des Kontexts | 41% |
| Kleinstes Dokument | 0% (verschwunden!) | 8% |
| Gini-Koeffizient | 0.68 | 0.42 |

*Code: `modules/citation_rag.py`, `generate_answer()` → Essence Parity Block*

## 6.3 Rescue Mission

**Szenario:** Ein Dokument hat nach dem Reranking 0 Chunks.
Mögliche Ursache: Language-Mismatch, thematische Randlage,
zu strenger Threshold.

**Mechanismus:** `_original_results_cache` speichert alle Chunks
*vor* dem Reranking. Bei 0 Chunks wird dieser Cache durchsucht
und die besten Pre-Reranking-Chunks des betroffenen Dokuments
wiederhergestellt — mit einem Mindest-Score-Filter (0.5)
um reine Rausch-Chunks zu vermeiden.

**Garantie:** Kein explizit ausgewähltes Dokument verschwindet vollständig.

---

# 7. HERMENEUTIC ENFORCER

## 7.1 Zwei-Dimensionale Validierung

**Standard-Fact-Checker:** Wahr / Falsch. Simpel, aber unzureichend.

**Hermeneutic Enforcer:** Bewertet jede Aussage in zwei unabhängigen Dimensionen.

### Dimension 1: Hermeneutische Ebene (Wie?)

| Kategorie | Bedeutung | Beispiel |
|---|---|---|
| `paraphrase` | Umformulierung gleicher Bedeutung | "Er negiert seine Existenz" für "Ich bin nichts" |
| `inference` | Logische Ableitung aus Text | "Der Boden wird nass" aus "Es regnet" |
| `meta` | Analyse von Stil oder Struktur | "Die Wiederholung erzeugt Rhythmus" |
| `hallucination` | Erfundener Fakt | Name/Datum nicht in Quelle |
| `false_quote` | Zitat das nicht in Quelle steht | Anführungszeichen, aber Text fehlt |

### Dimension 2: Validitäts-Ebene (Korrekt?)

| Kategorie | Bedeutung |
|---|---|
| `supported` | Quelle bestätigt die Aussage direkt |
| `contradiction` | Quelle widerspricht der Aussage |
| `exaggeration` | Kern stimmt, aber übertrieben ("leichte Vorteile" → "10× besser") |
| `unsupported` | Aussage steht nicht in der Quelle |
| `temporal_fiction` | Erfundene Zeitangaben oder Versionsnummern |

### Entscheidungs-Matrix (Beispiele)

| Hermeneutisch | Validität | Ergebnis | Bedeutung |
|---|---|---|---|
| `paraphrase` | `supported` | ✅ gültig | Korrekte Umformulierung |
| `inference` | `exaggeration` | ❌ ungültig | Schlussfolgerung übertrieben |
| `hallucination` | `unsupported` | ❌ ungültig | Erfundener Fakt |
| `meta` | `supported` | ✅ gültig | Valide Stilanalyse |
| `false_quote` | `unsupported` | ❌ ungültig | Zitat existiert nicht |

## 7.2 Multi-Source-Validierung

Sätze, die aus mehreren Quellen gleichzeitig zitieren
(z.B. "Wie X [1] und Y [2] übereinstimmen..."), werden gegen
die *Summe* aller genannten Quellen geprüft. Das Zitat gilt als
valide, wenn es in *mindestens einer* der genannten Quellen vorkommt.

## 7.3 Caching

Identische Claim+Quelle-Kombinationen werden gecacht
(MD5-Hash). Wiederholte Validierungen kosten ~0.0002s
statt eines neuen LLM-Calls.

---

# 8. IMPORTER

## 8.1 Unterstützte Formate

| Format | Plattformen/Typen |
|---|---|
| HTML | ChatGPT, Claude, DeepSeek, Kimi, Grok, Perplexity, Gemini |
| PDF | Wissenschaftliche Artikel, Bücher (PyMuPDF) |
| EPUB | E-Books (ebooklib) |
| TXT | Plain Text |
| MD | Markdown (neu v50.9+) |
| JSON | Generisches Chat-JSON |
| FB2 | FictionBook-Format |

## 8.2 Metadaten-Extraktion

Beim Import werden automatisch extrahiert:
- **Datum** (`real_date_str`): aus Dateiname oder Inhalt ("13.10.2025", "Mai 2025")
- **Version** (`version`): aus Modell-/Titelangaben
- **Sprecher** (`model_name`): aus Plattform-spezifischen HTML-Strukturen

Diese Metadaten ermöglichen die **chronologische Synthese** —
Antworten folgen einem Zeitstrahl statt reiner Relevanz-Sortierung.

---

# 9. ANALYSE-MODI

## 9.1 Standard-Modi

| Modus | Ausgelöst durch | Charakteristik |
|---|---|---|
| FACTUAL | "Was ist X?", Definitionen | Präzision, enger Kontext |
| LITERARY | Gedichte, Essays, Stilanalyse | Breiter Kontext, Nuancen |
| ANALYTICAL | "Vergleiche A und B" | Balance zwischen Breite und Tiefe |

## 9.2 ANALYTICAL_FORENSIC — Der Forensiker

Für kritische Gegenlektüre und Dekonstruktion.

**Trigger-Formulierungen:**
- "Warum hat X seine Meinung geändert?"
- "Was verschweigt dieser Text?"
- "Welche Interessen stecken hinter dieser Position?"
- "Lies gegen den Strich"

**Erzwungene Ausgabe-Struktur:**
1. **BEFUND** — Welche zentralen Aussagen oder Widersprüche zeigen die Quellen?
2. **RHETORISCHE STRATEGIE** — Wie rahmt der Text diese Positionen?
3. **FUNKTIONALES MOTIV** — Welches Problem löst diese Rahmung?
4. **DISKURSIVE KONSEQUENZ** — Was wird dadurch legitimiert oder unsichtbar gemacht?
5. **FAZIT** — Strukturelle Erkenntnisse, keine Harmonisierung

**Wichtig:** Der Forensiker harmonisiert nicht. Widersprüche werden benannt,
nicht aufgelöst.

---

# 10. PERFORMANCE & GRENZEN

## 10.1 Metriken (v52, lokaler Betrieb)

| Metrik | Wert | Erklärung |
|---|---|---|
| Query-Zeit (lokal, 9B) | 2–8 Minuten | LLM-Calls dominieren |
| Query-Zeit (lokal, 27B) | 5–15 Minuten | Abhängig von VRAM/Quantisierung |
| Embedding-Speed | ~500 Chunks/min | GPU empfohlen |
| Retrieval-Precision | 85–90% | Hybrid Search + VIP |
| Enforcer-False-Positives | <20% | Zwei-dimensionale Validierung |

**Warum so langsam?**
Das ist kein Bug, sondern ein bewusster Tradeoff. Jede Analyse durchläuft:
Query Expansion + Hybrid Retrieval + Reranker (N LLM-Calls) + Synthese + optionaler Enforcer.
Die Engine ist für Tiefe optimiert, nicht für Echtzeit.

## 10.2 Bekannte Grenzen

**1. Chronologie braucht Metadaten**
Datum-Extraktion funktioniert für Chat-Exporte gut. Bei literarischen Texten
ohne Zeitangabe fällt die Sortierung auf "undatiert" zurück.

**2. VRAM-Grenzen**
Für 9B-Modelle empfehlen wir min. 6 GB VRAM.
Für 27B-Modelle min. 16 GB.
Die `.env` bietet `LOCAL_RERANKER_CANDIDATES` und `LOCAL_MAX_CHUNKS`
als VRAM-Schutz.

**3. Optimal für <100 kuratierte Texte**
Die Engine ist nicht für Millionen-Dokument-Indizes optimiert.
Für >100 Texte steigen Query-Zeiten und Reranker-Kosten spürbar.

**4. Imbalance-Warnung statt automatischer Korrektur**
Das System erkennt Chunk-Ungleichgewichte und warnt —
automatische Vollkorrektur ist noch nicht vollständig implementiert.

---

# 11. DEPLOYMENT

## 11.1 Lokaler Betrieb (Standard)

```bash
# Einmalige Einrichtung
cp .env.example .env
# LM Studio starten + Modell laden

# Starten
streamlit run app.py --server.port 8503
```

## 11.2 Cloud-Deployment (Optional)

Für Cloud Run oder ähnliche Dienste: `LLM_BACKEND=vertex` oder
`LLM_BACKEND=openai` in `.env` setzen und entsprechende Credentials
als Environment-Variablen konfigurieren. Siehe `.env.example`.

**Port-Konfiguration für Cloud Run:**
```
# Procfile
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

## 11.3 Troubleshooting

| Problem | Ursache | Lösung |
|---|---|---|
| "Connection refused" | LM Studio nicht aktiv | LM Studio starten + Server aktivieren |
| Leere Antworten | Modell nicht geladen | Modell in LM Studio auswählen |
| Sehr langsame Embedding | Kein GPU gefunden | Normales Verhalten; GPU installieren optional |
| "No chunks found" | Noch keine Imports | Import-Tab: Chat-Export hochladen |

---

# 12. ROADMAP

## Umgesetzte Meilensteine (v48 – v52)

- ✅ v48: Core RAG-Pipeline, Importer
- ✅ v49: Hybrid Search RRF, Hermeneutic Enforcer v1
- ✅ v50.5: VIP-Schutz, Essence Parity, Investigativ-Modus
- ✅ v50.7: Chronologische Synthese, logarithmische Chunks, Thread-Safety
- ✅ v50.9: ANALYTICAL_FORENSIC, Multi-Source-Enforcer, Public Launch
- ✅ v52: Local-First Release, `.env.example`, bereinigter Code

## Geplant für v53+

- **Local-Model Feintuning:** Spezifische Prompt-Optimierungen für kleinere Open-Weights (z.B. Llama-3-8B).

---

# 13. ANHÄNGE

## 13.1 Credits

**Project Lead:** Grigori Pantijelew (Landesinstitut für Schule Bremen)

**KI-Entwicklungs-Team:**
- **Claude Sonnet 4.6 (Anthropic):** Architektur-Konzepte, Design-Patterns, Code-Review
- **Gemini (Google):** Code-Implementierung, SDK-Migration, Debugging
- **Kimi (Moonshot AI):** Lektorat aller Texte und Dokumentation

**Infrastruktur:** Google Cloud Platform (Research Credits Program)

---

## 13.2 Glossar

| Begriff | Bedeutung |
|---|---|
| **Chunk** | Textsegment (typisch 300–500 Tokens), atomare Indexierungseinheit |
| **Essence Parity** | Logarithmische Fairness-Quota pro Dokument |
| **Gini-Koeffizient** | Maß für Ungleichheit (0 = perfekt fair, 1 = maximal unfair) |
| **Hermeneutic Enforcer** | Zwei-dimensionaler Validierungs-Kern |
| **Hermeneutic Router** | Intent-Klassifizierungs-Modul |
| **Investigativ-Modus** | Retrieval-Strategie für kleine Korpora (≤5 Dokumente) |
| **RRF** | Reciprocal Rank Fusion — Algorithmus zur Ranking-Kombination |
| **VIP-Schutz** | Garantiert top-3 Chunks pro ausgewähltem Dokument |
| **Rescue Mission** | Fallback-Mechanismus bei 0 Chunks nach Reranking |

---

## 13.3 Kontakt

**Projekt-Lead:** Grigori Pantijelew
**Email:** hermeneutic-engine@proton.me
**Repository:** https://github.com/gpantijelew/hermeneutic-engine
**Preprint:** https://doi.org/10.5281/zenodo.18774828

---

**Ende der FIBEL v52**
*Stand: 2026 | Lizenz: MIT*
