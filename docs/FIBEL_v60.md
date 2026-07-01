# 📘 FIBEL — HERMENEUTIC RECONSTRUCTION ENGINE
## Vollständige Dokumentation: Konzepte, Architektur, Betrieb

**Version:** v60 "Falsifizierungs-Architektur"
**Stand:** Juli 2026
**Autor:** Grigori Pantijelew (Project Lead)
**KI-Team:** Claude Sonnet 4.6 (Architektur), Gemini und GLM (Code), Kimi (Lektorat)

**Status:** ✅ Production-Ready

---

## 🎯 Inhaltsverzeichnis

1. **PROJEKT-IDENTITÄT** — Mission, Evolution, Was ist neu in v60?
2. **KONZEPTIONELLE GRUNDLAGEN** — Hermeneutik, Fairness, Architektur-Philosophie
3. **SCHNELLSTART** — Lokale Installation, erste Analyse
4. **TECHNISCHE ARCHITEKTUR** — Core-Module, Datenbank, Konfiguration
5. **RAG-PIPELINE** — Retrieval, Reranking, Synthese, Validierung
6. **FAIRNESS-MECHANISMEN** — VIP-Schutz, Essence Parity, Rescue Mission
7. **HERMENEUTIC ENFORCER** — Zwei-dimensionale Validierung
8. **IMPORTER** — Unterstützte Formate und Plattformen
9. **ANALYSE-MODI** — Vom Fakten-Check zum forensischen Blick
10. **STILISTIC LAB** — Stilistische Analyse mit Etappen-Architektur (v57)
11. **META-ENGINE** — Meta-Analyse, Meta-Vergleich, Meta-Meta (v59–v60)
12. **FALSIFIZIERUNGS-ARCHITEKTUR** — Agency, Gegenposition, Adjudikation (v60)
13. **PERFORMANCE & GRENZEN** — Metriken, bewusste Tradeoffs
14. **DEPLOYMENT** — Lokal, Cloud optional
15. **ROADMAP & OFFENE FRAGEN**
16. **ANHÄNGE** — Credits, Glossar, Kontakt

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

Standard-RAG-Systeme leiden unter drei fundamentalen Schwächen:

**1. Source Bias:** Große Texte überschatten kleine.
Ein 200-seitiger Text erzeugt ~500 Chunks — ein 7-seitiger Essay nur ~10.
Das Ergebnis: Der Essay verschwindet aus der Synthese, obwohl er für die
Frage gleichwertig relevant ist.

**2. Validation Blindness:** Synthesen enthalten Halluzinationen —
erfundene Zitate, falsche Daten, unbelegte Behauptungen —
die von legitimen Inferenzen nicht unterscheidbar sind.

**3. Confirmation Bias:** Eine Pipeline, die nur bestätigt, wird
zur Bestätigungsmaschine. Sie findet das, was sie finden soll,
und übersieht das, was die Hypothese infrage stellt.

### Unsere Antwort: Architektonische Garantien

Die Hermeneutic Engine löst diese Probleme nicht durch bessere Prompts,
sondern durch vier architektonische Garantien:

| Ebene | Mechanismus | Garantie |
|---|---|---|
| Retrieval | VIP-Schutz + Investigativ-Modus | Jedes ausgewählte Dokument erscheint |
| Synthese | Essence Parity (logarithmisch) | Keine Quelle dominiert durch Größe |
| Validierung | Hermeneutic Enforcer (2D) | Halluzinationen < 20% false positives |
| **Falsifizierung (v60)** | **Gegenposition + Adjudikation + revidierte Destillation** | **Die Engine kann ihre eigene These in Frage stellen** |

---

## 1.3a Demos & Fallstudien

### Fallstudie: Sigmund Freud und die Verführungstheorie

Das YouTube-Video zur ersten öffentlichen Demonstration der Engine analysiert
vier Primärtexte Freuds (1896–1924) in unter zwei Minuten:

- *Zur Ätiologie der Hysterie* (1896): Freud verteidigt die Verführungstheorie
  als empirischen Befund
- Brief an Wilhelm Fliess (21.09.1897): das private Dokument — der Bruch,
  ohne Publikum, ohne Pose
- *Drei Abhandlungen zur Sexualtheorie* (1905 und 1924): das stille Umschreiben
  über zwei Jahrzehnte

Der Modus: `ANALYTICAL_FORENSIC`. Die Engine fragt nicht, was Freud behauptete —
sie fragt, was er verschleierte und wie er den Rückzug als intellektuelle
Courage inszenierte. Der Enforcer flaggt anschließend, wo die Engine selbst
überschießt: halluzinierte Metadaten, nicht belegte Verstärker. Zweiter Schritt: Die Engine kommt zu selben Ergebnissen auch ohne den Flies-Brief.

> **Epistemic Hygiene: Eine KI, die ihre eigenen Fehler benennt.**

### Fallstudie: Imperiale Rhetorik bei Puschkin, Blok, Brodsky (v60)

Die zweite Fallstudie (in Vorbereitung als DOI-Paper) wendet die v60-Falsifizierungs-Architektur
auf sechs Gedichte von drei russischen Lyrikern an. Die Ausgangshypothese lautete:
"Imperiale Rhetorik entsteht bei Lyrikern aus liberalen/lyrischen Anfängen — eine
Radikalisierung der Autoren."

Die Engine widerlegt diese Hypothese für alle drei Fälle — nicht durch externen
Eingriff, sondern durch ihre eigene Gegenprobe. Das Ergebnis ist eine Reframierung:
Statt "Radikalisierung der Autoren" spricht die revidierte Destillation von einer
"Genealogie sprachlicher Operationen". Die Beobachtung der Transformation hält
stand; die Interpretation als Radikalisierung wird widerrufen.

> **Falsifikation als architektonisches Prinzip: Eine KI, die ihre eigene These widerlegt.**

---

## 1.3b Was ist neu in v60?

v60 ist die erste Version mit einer **Falsifizierungs-Architektur** — die
Meta-Ebene wird um eine systematische Gegenprobe erweitert.

| Aspekt | v52 (Public Launch) | v57 | v58 | v59 | **v60** |
|---|---|---|---|---|---|
| Standard-Backend | LM Studio (Port 1234) | ✓ | ✓ | ✓ | ✓ |
| Standard-Modell | `qwen3.5-9b-highiq-instruct` | ✓ | ✓ | ✓ | ✓ |
| Analysemodi | 4 (FACTUAL, LITERARY, ANALYTICAL, FORENSIC) | +1 (STILISTIC) | ✓ | ✓ | ✓ |
| Pro-Quelle-Extraktion | — | ✓ | ✓ | ✓ | ✓ |
| Verify-Gate | — | ✓ | ✓ | ✓ | ✓ |
| Modus-Erkennung | — | — | ✓ | ✓ | ✓ |
| Tynjanow-Integration | — | — | ✓ | ✓ | ✓ |
| META-VERGLEICH | — | — | — | ✓ | ✓ |
| **Agency-Extraktion** | — | — | — | — | **✓** |
| **Quellen-Gegenposition (dormant)** | — | — | — | — | **✓** |
| **Meta-Gegenposition** | — | — | — | — | **✓** |
| **Meta-Adjudikation** | — | — | — | — | **✓** |
| **Revidierte Destillation** | — | — | — | — | **✓** |
| **Freie Frage (Option B — VOLLANALYSE)** | — | — | — | — | **✓** |
| **Meta-Meta-Ebene** | — | — | — | — | **✓** |

### v60-Highlights im Detail

1. **Falsifizierungs-Architektur** (vier Schritte):
   - Agency-Extraktion pro Meta-Run (intentional / responsiv / entbündelnd)
   - Quellen-Gegenposition (dormant in STILISTIC LAB)
   - Meta-Gegenposition (Strang B) — argumentiert GEGEN die These der Bestätigung
   - Meta-Adjudikation (Strang C) — bewertet, was standhält; KEINE Harmonisierung
   - Revidierte Destillation — synthetisiert nur, was der Gegenprobe standhält

2. **Freie Frage (Option B):** Schneller Modus (nur SEZIEREN + FREIE FRAGE) oder
   VOLLANALYSE-Modus (alle Stränge inkl. Adjudikation, dann Freie Frage auf
   adjudizierte Daten).

3. **2D-Framework (Modus × Agency-Qualität):** Forschungsplanungs-Raster mit
   3 besetzten und 3 leeren Feldern als explizite Forschungslücken.

4. **Meta-Meta-Ebene:** Vergleich von 15 Meta-Läufen über Engine-Versionen
   hinweg. Diagnostiziert Bestätigungs-Bias (13/15 Läufe), Engine-Entwicklung
   (Mustererkennung → kritische Selbstkorrektur) und Agency-Stabilität (1–2/15 Runs).

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
- **Falsifizierungs-Architektur (v60):** Die Engine produziert eine
  Gegenposition zu ihrer eigenen Primäranthese und adjudiziert
  zwischen beiden.

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
| Hermeneutik | Warum so? | Synthesis-Prompt, Forensik-Modus, Falsifizierungs-Architektur |

---

## 2.4 Falsifizierung als architektonisches Prinzip (v60)

### Das Problem der Bestätigungsmaschine

Jede Analysepipeline, die nur bestätigt, produziert Bestätigung als Output —
unabhängig davon, ob die Hypothese stimmt oder nicht. Das ist kein Bug,
sondern eine strukturelle KI-Eigenschaft: Die Pipeline *soll* die Hypothese
prüfen, aber wenn sie nur Bestätigungskanäle hat, kann sie nur bestätigen.

### Die Lösung: Strukturelle Gegenposition

v60 führt eine **vier-Schritt-Gegenprobe** ein, die nicht nachträglich
eingreift, sondern strukturell in die Pipeline eingebaut ist:

```
Strang A (bestätigend)      Strang B (falsifizierend)      Strang C (bewertend)
   BEOBACHTEN                   GEGENPOSITION                   ADJUDIKATION
       ↓                            ↓                              ↓
       └──────────────────────────┬───────────────────────────────┘
                                  ↓
                         REVIDIERTE DESTILLATION
                                  ↓
                          FINALE THESE
                       (kann Ursprungs-
                        these modifizieren
                        oder widerlegen)
```

**Wichtig:** Die Adjudikation ist KEINE Harmonisierung. Sie bewertet,
was von Bestätigung und Gegenposition standhält und was nicht —
die Spannung bleibt bestehen, sie wird nicht aufgelöst.

### Hermeneutischer Status

Die Falsifizierung ist **kein Beweis**, sondern eine **architektonische
Gewährleistung**:

- Die Engine *kann* ihre These widerlegen — sie *muss* es nicht.
- Wenn die These standhält, ist sie stärker abgesichert als ohne Gegenprobe.
- Wenn die These fällt, ist das selbst ein Befund — die Engine hat
  ihre eigene Voreingenommenheit erkannt.

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
(ChatGPT, Claude, DeepSeek, Kimi, Grok, etc.) oder ein literarisches
Korpus (TXT, MD, PDF, EPUB, FB2).

**Schritt 2 — Analyse:**
Navigiere zu "Analyse" → Wähle deine importierten Dokumente aus →
Stelle eine Frage auf Deutsch oder Englisch.

Für stilistische Vergleiche: Navigiere zu "STILISTIC LAB" →
Lade 2–6 Quellen → Wähle eine Forschungsfrage.

Für Meta-Analyse: Navigiere zu "Destillation" → Wähle 4–15
STILISTIC-LAB-Ergebnisse → Wähle Modus (VOLLANALYSE, FREIE FRAGE,
META-VERGLEICH).

**Schritt 3 — Tiefenprüfung (optional):**
Klappe "Enforcer Protokoll" auf → Klicke "Tiefenprüfung starten" →
Jede Aussage wird gegen die Quellen validiert.

Für Falsifizierung (v60): Aktiviere im Destillation-Tab die
"VOLLANALYSE"-Option — die Pipeline läuft automatisch mit
Gegenposition und Adjudikation.

---

# 4. TECHNISCHE ARCHITEKTUR

## 4.1 Modul-Übersicht

```
hre-vertex-engine/
├── app.py                         # Einstiegspunkt: Auth, Navigation, Routing
├── modules/
│   ├── config.py                  # Zentrale Konfiguration, Modell-Registry, ENGINE_VERSION
│   ├── database.py                # SQLite + FTS5 (Chat-Verwaltung)
│   ├── vector_store.py            # ChromaDB + BM25 (Vektorsuche, RRF)
│   ├── citation_rag.py            # RAG-Orchestrator (Retrieval → Synthese)
│   ├── hermeneutic_router.py      # Intent-Klassifizierung (6 Intents)
│   ├── hermeneutic_reranker.py    # LLM-as-Judge
│   ├── hermeneutic_enforcer.py    # Zwei-dimensionale Validierung
│   ├── llm_wrapper.py             # Universeller LLM-Client (alle Backends)
│   ├── llm_instructions.py        # System-Prompts (DISCOURSE, EXEGESIS)
│   ├── text_analyzer.py           # [v57] Deterministische Textstatistiken
│   ├── stilistic_lab_pipeline.py  # [v57] STILISTIC LAB Pipeline + Meta-Vergleich
│   ├── meta_hermeneutic_engine.py # [v59/v60] Meta-Engine + Falsifizierungs-Architektur
│   └── importers/                 # Parser für verschiedene Chat-Formate
├── ui/
│   ├── state.py                   # Zentrales Session State Management
│   ├── chat_tab.py                # Chat-Interface
│   ├── analysis_tab.py            # Analyse-Pipeline-UI
│   ├── import_tab.py              # Import-Interface
│   ├── pipeline_trace.py          # Pipeline-Transparenz-UI
│   ├── stilistic_lab_tab.py       # [v57] STILISTIC LAB UI
│   ├── destillation_tab.py        # [v59/v60] Meta-Destillation + Freie Frage + Meta-Vergleich
│   └── ...
├── hre_data/
│   ├── hre.db                     # SQLite-Datenbank
│   └── chroma/                    # ChromaDB-Vektordaten
└── .env                           # Lokale Konfiguration (nicht eingecheckt)
```

## 4.2a Code-Architektur: Vom Monolithen zum Orchestrator

Die v52 enthielt neben dem inhaltlichen Upgrade ein substantielles
**Architektur-Refactoring**, das für die Open-Source-Community entscheidend ist.

**Das Problem in v50.x:** Die `app.py` war mit ~1.200 Zeilen ein Monolith —
Routing-Logik, UI-Rendering, State-Management und Fehlerbehandlung waren
untrennbar verwoben.

**Die Lösung seit v52:** `app.py` ist ein schlanker **Orchestrator**.
Die gesamte UI-Logik ist in domänenspezifische Module ausgelagert:

- `ui/state.py` — Zentrales Session-State-Management
- `ui/chat_tab.py` — Chat-Interface
- `ui/analysis_tab.py` — Analyse-Pipeline
- `ui/import_tab.py` — Import-Interface
- `ui/pipeline_trace.py` — Pipeline-Transparenz-UI
- `ui/stilistic_lab_tab.py` (v57) — STILISTIC LAB
- `ui/destillation_tab.py` (v59/v60) — Meta-Destillation, Freie Frage, Meta-Vergleich

Jedes UI-Modul ist isoliert testbar und austauschbar. Ein neues Import-Format,
eine erweiterte Enforcer-Ansicht, ein angepasstes Analyse-Layout — das berührt
genau *ein* Modul, nicht den gesamten Stack.

## 4.2b LLM-Backends

Die Engine unterstützt exemplarisch drei Backends, konfigurierbar via `.env`(viele andere sind möglich):

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
         Intent: FACTUAL / LITERARY / ANALYTICAL / ANALYTICAL_FORENSIC / STILISTIC
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
und klassifiziert den Intent. Seit v57 gibt es fünf Intents
(plus drei Meta-Intents, die nicht über den Router laufen, sondern
direkt vom Destillation-Tab getriggert werden).

| Intent | Threshold | Limit | Einsatz |
|---|---|---|---|
| `FACTUAL` | 0.75 | 15 | Definitionen, Daten, "Was ist X?" |
| `LITERARY` | 0.45 | 40 | Essays, Lyrik, Stil, Atmosphäre |
| `ANALYTICAL` | 0.60 | 30 | Vergleiche, Entwicklungen, "X vs. Y" |
| `ANALYTICAL_FORENSIC` | 0.45 | 35 | Dekonstruktion, Motivanalyse, kritische Gegenlektüre |
| `STILISTIC` (v57) | — | — | Stilistische Mehr-Quellen-Analyse mit Etappen-Architektur |
| `META` (v59/v60) | — | — | Meta-Analyse bestehender STILISTIC-Ergebnisse |
| `META_VERGLEICH` (v59) | — | — | Werkzeugvergleich zweier Analysen |

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
| MD | Markdown (seit v50.9) |
| JSON | Generisches Chat-JSON |
| FB2 | FictionBook-Format |

## 8.2 Metadaten-Extraktion

Beim Import werden automatisch extrahiert:
- **Datum** (`real_date_str`): aus Dateiname oder Inhalt ("13.10.2025", "Mai 2025")
- **Version** (`version`): aus Modell-/Titelangaben
- **Sprecher** (`model_name`): aus Plattform-spezifischen HTML-Strukturen
- **Autor** (`author`): [v57] aus Sidecar-`.md`-Datei oder First-Line-Heuristik

Diese Metadaten ermöglichen die **chronologische Synthese** —
Antworten folgen einem Zeitstrahl statt reiner Relevanz-Sortierung.
Die Autor-Zuordnung ist Voraussetzung für die Agency-Extraktion (v60).

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

# 10. STILISTIC LAB (v57)

> STILISTIC LAB ist der Analysemodus für **stilistischen Vergleich** zwischen
> mehreren Quellen. Er wurde in v57 eingeführt und in v58 um die Tynjanow-Integration
> erweitert. STILISTIC LAB ist die **Primärebene**, auf der die Meta-Engine (v59/v60)
> aufsetzt.

## 10.1 Drei-Etappen-Architektur

```
Etappe 1 — SEZIEREN (100% Python, 0% LLM)
   ├ Satzbau (HS/NS, Ø/Median/Max-Satzlänge)
   ├ Satzzeichen-Verteilung
   ├ Type-Token-Ratio (TTR + STTR)
   ├ Top-Wörter, Bigramme, Trigramme
   ├ Morphologische Komplexität pro Satz
   ├ Hotspot-Sätze (längste/kürzeste/inhaltlich dichteste)
   ├ Alliterationen
   └ Enjambements (für Lyrik)
       ↓
Etappe 2 — EINORDNEN (LLM interpretiert Python-Daten)
   ├ DIE DOMINANTE — "Was hält den Rest zusammen?"
   ├ BEOBACHTUNG — Fließ-Anweisung, 2-3 Beobachtungen mit Zitat-Beleg
   ├ VERTIEFUNG — "Was wird erst sichtbar, wenn man die Dominante wegdenkt?"
   └ STIL-TITEL — "Schreibe den TITEL dieses Stils"
       ↓
Etappe 3 — FREIER RAUM (LLM macht kreativen Sprung)
   └ Freie Assoziation, über das Corpus hinaus
       ↓
Globale Synthese (5 Sektionen, v58):
   1. HYPOTHESE — Falsifizierbare Vorab-These
   2. BEWEISFÜHRUNG — Strukturelle Argumentation
   3. KENNZAHLEN-ÜBERRASCHUNG — Was überrascht an den Daten?
   4. FREIER RAUM — Kreativer Sprung
   5. FAZIT — Strukturelle Erkenntnis, keine Harmonisierung
```

## 10.2 Kernprinzip: Python zählt, LLM charakterisiert

STILISTIC LAB trennt strikt zwischen **Messung** (Python) und
**Interpretation** (LLM). Das LLM darf nicht zählen — es darf nur
charakterisieren, was Python gezählt hat. Diese Trennung verhindert,
dass das LLM seine Intuition als Messung verkauft.

## 10.3 Pro-Quelle-Extraktion + Verify-Gate (v57)

Statt eines Monolith-Calls (1×28K Token für 6 Quellen) verwendet
STILISTIC LAB **6×5K Calls** — einen pro Quelle. Vorteile:

- **Volle Attention pro Dokument** — kein Attention-Verlust bei >20K Token
- **Garantiert ≥2 Zitate/Quelle** — die Pro-Quelle-Prompt-Struktur erzwingt Belege
- **Verify-Gate** — Substring-Existenz-Prüfung vor Synthese: Zitate, die nicht
  buchstabengetreu in der Quelle stehen, werden zurückgewiesen

## 10.4 Modus-Erkennung (v58)

Vor der Analyse wird eine **Modus-Erkennung** als Vorentscheidung durchgeführt.
Der Modus bestimmt, welche Analyseachsen relevant sind:

| Modus | Indikator |
|---|---|
| **Polemik** | Direkte Adressierung, Invektiven, Wertung |
| **Beschwörung** | Sakralsprache, Imperativ, Anaphern |
| **Nachdenken** | Hypotaxe, Konditional, Reflexivität |
| **Erzählen** | Narrativ, Tempus-Wechsel, Detaildichte |
| **Spiel** | Ironie, Paradox, Metrik-Bruch |

## 10.5 Tynjanow-Integration (v58)

Auf Basis von Jurij Tynjanows literaturwissenschaftlicher Theorie:

- **GRUNDOPERATION als zweite Analyseachse** (neben DOMINANTE)
  - *Struktur* = "Der Text stellt X und Y gegenüber"
  - *Operation* = "Der Text zerstört X durch die Berührung mit Y"
  - Die Pipeline fragt nicht, was der Text VERWENDET (Figuren),
    sondern was er TUT (Operationen).

- **OPERATIONS-GENEALOGIE in der Synthese** — Wie entwickeln sich Operationen
  über mehrere Quellen hinweg?

- **FREIER RAUM als optionale Meta-Ebene** — Der kreative Sprung ist nicht
  Pflicht, sondern Möglichkeit.

## 10.6 Verdichtungsschicht (v58)

Vor dem 4000-Wörter-Volltext steht eine **48-Wörter-Verdichtung**:
Regex extrahiert pro Quelle die wichtigsten Labels (Dominante, Grundoperation,
Modus, Stil-Titel) als informationsarchitektonische Eingang.

Das LLM sieht die Verdichtung zuerst und kann so den Volltext mit
strukturellem Vorwissen lesen — nicht umgekehrt.

---

# 11. META-ENGINE (v59–v60)

> Die Meta-Engine analysiert **bestehende STILISTIC-LAB-Ergebnisse** — sie
> ist keine Primäranalyse, sondern eine Analyse von Analysen. Eingeführt in
> v59 (META-VERGLEICH), erweitert in v60 um die Falsifizierungs-Architektur.

## 11.1 Drei Modi der Meta-Engine

### Modus 1: VOLLANALYSE (v60 — Default)

Vergleicht 4–15 STILISTIC-LAB-Ergebnisse und produziert eine
Meta-Synthese über alle hinweg. Seit v60 mit Falsifizierungs-Architektur
(siehe Abschnitt 12).

```
SEZIEREN (pro Run)
   ↓
TERMINI (Akteur-Extraktion)
   ↓
BEOBACHTEN (Strang A — bestätigend)
   ↓
GEGENPOSITION (Strang B — falsifizierend, v60)
   ↓
ADJUDIKATION (Strang C — bewertend, v60)
   ↓
DESTILLATION (revidiert, v60)
   ↓
FREIE FRAGE (optional)
```

### Modus 2: FREIE FRAGE (Option B — v60)

Stellt eine gezielte Frage zu den SEZIEREN-Daten, ohne die volle
Pipeline zu durchlaufen. Zwei Sub-Modi:

- **Option B1 (schnell):** Nur SEZIEREN + FREIE FRAGE — für kurze
  Auswertungen ohne Falsifizierungs-Aufwand
- **Option B2 (VOLLANALYSE):** Alle Stränge inkl. Adjudikation, dann
  Freie Frage auf die adjudizierten Daten — für Fragen, die eine
  methodisch abgesicherte Antwort brauchen

### Modus 3: META-VERGLEICH (v59)

Vergleicht *zwei* analytische Verfahren (z.B. zwei verschiedene
STILISTIC-LAB-Konfigurationen) auf Methode und Leistung.
5-Achsen-Protokoll:

1. **Konvergenzen** — Wo kommen beide Verfahren zum gleichen Ergebnis?
2. **Divergenzen** — Wo weichen sie ab?
3. **Komplementarität** — Wo ergänzen sie sich?
4. **Grenzen** — Wo versagen beide?
5. **Systematischer Ertrag** — Was lernen wir über das Feld?

**Architektur:** Einzel-LLM-Call (Inputs = bereits Analysen, keine Pipeline).
**Anti-Harmonisierung:** Werkzeugvergleich, nicht Rangierung.

## 11.2 SEZIEREN — Was wird pro Run extrahiert?

Für jeden STILISTIC-LAB-Run werden automatisch folgende Felder extrahiert:

| Feld | Quelle |
|---|---|
| `run_nr` | Header |
| `version` | Header (z.B. v2.7.1) |
| `dauer` | Header (gesamte Laufzeit) |
| `modelle` | Header (welche LLM-Modelle) |
| `etappe1_vorhanden` | Boolean — sind Etappe-1-Daten vorhanden? |
| `stufen_dauer` | Dict — Dauer pro Pipeline-Stufe (alle 7 Stufen, v60) |
| `source_type` | Metadaten |
| `meta_version` | Header |
| `autor` | Sidecar / Metadaten (v57+) |
| `agency_qualitaet` | Mini-LLM-Extraktion (v60) |

## 11.3 TERMINI — Akteur-Extraktion

Pro Run werden die zentralen Termini (Akteure, Konzepte, Fachbegriffe)
extrahiert. Diese bilden die **Cluster-Achse** der Meta-Analyse:
Welche Akteure tauchen in welchen Runs auf? Welche nur in frühen, welche
nur in späten?

---

# 12. FALSIFIZIERUNGS-ARCHITEKTUR (v60)

> Die Falsifizierungs-Architektur ist das **methodische Herzstück** von v60.
> Sie macht die Engine zu einem System, das seine eigene Ausgangshypothese
> widerlegen kann — und in den durchgeführten Testläufen auch widerlegt.

## 12.1 Die vier Schritte

### Schritt 1 — Agency-Extraktion

Pro Meta-Run wird die Agency-Qualität (intentional / responsiv / entbündelnd)
über ein **kontrolliertes Mini-LLM** extrahiert. Agency-Qualitäten sind
kontrollierte Vokabular-Werte — keine freien Substantiv-Phrasen. Damit
sind sie aggregierbar, aber explizit als *hermeneutische Interpretation*
gekennzeichnet, nicht als HRE-Messwert.

| Agency-Qualität | Bedeutung |
|---|---|
| **intentional** | Der Autor *wählt* und steuert die Rhetorik aktiv |
| **responsiv** | Der Autor *antwortet* auf etwas, das ihn übersteigt; formt in Resonanz |
| **entbündelnd** | Der Autor *entzieht* Steuerung mit kühler Geste; kalkulierter Entzug |
| `null` | Run kennt die Agency-Kategorien nicht (ältere Engine-Variante) — selbst ein Befund |

**Wichtig:** Runs ohne Agency-Information geben `null` zurück. `null` ist selbst
ein Befund — diese Runs kennen die Agency-Kategorien nicht.

### Schritt 2 — Quellen-Gegenposition (dormant)

Die STILISTIC-LAB-Pipeline erhält einen **schlafenden Strang-B-Eingang**,
der auf Etappe-1-Daten eine Gegenposition zur Primäranthese formulieren kann.
Wird nicht automatisch getriggert, sondern über Freie Frage (Option B)
verfügbar.

### Schritt 3 — Meta-Gegenposition (Strang B)

META-GEGENPOSITION als eigener Intent in `hermeneutic_protocol.yaml`.
Argumentiert auf Meta-Ebene GEGEN die These der bestätigenden Pipeline.

**Wichtige architektonische Entscheidung:** Die Meta-Gegenposition bekommt
nur die **Fragestellung** der Quellen-Gegenposition als Kontext, nicht
deren Antworten. Das vermeidet Bestätigungsdruck — Strang B muss seine
eigene Argumentation aufbauen, nicht die der Quellen-Gegenposition
nacherzählen.

### Schritt 4 — Meta-Adjudikation (Strang C) + revidierte Destillation

META-ADJUDIKATION als eigener Intent. Bewertet, was von Bestätigung (A)
und Gegenposition (B) standhält und was nicht.

**Kritisch:** Adjudikation ist KEINE Harmonisierung. Sie **bewertet**,
sie **versöhnt nicht**. Die Spannung zwischen Bestätigung und Gegenposition
bleibt erhalten — das ist der Punkt.

Die **revidierte Destillation** synthetisiert nur das, was der Gegenprobe
standhält. Die Ursprungs-These kann durch diese Destillation modifiziert
oder widerlegt werden.

## 12.2 Das 2D-Framework: Modus × Agency-Qualität

Die Falsifizierungs-Architektur verwendet ein **2D-Framework** als
Forschungsplanungs-Raster:

| Modus \ Agency | intentional | responsiv | entbündelnd |
|---|---|---|---|
| **Entstehung** | ✅ Fall 1 | (Forschungslücke) | (Forschungslücke) |
| **Transformation** | (Forschungslücke) | ✅ Fall 2 | (Forschungslücke) |
| **Enthüllung** | (Forschungslücke) | (Forschungslücke) | ✅ Fall 3 |

Drei Felder sind besetzt (die drei Testfälle), drei bleiben als
**explizite Forschungslücken** markiert. Das ist kein Mangel, sondern
eine methodische Aussage: Die Engine hat drei Fälle analysiert, und
die anderen sechs Kombinationen sind offene Fragen.

## 12.3 Die Meta-Meta-Ebene

Vergleicht mehrere Meta-Läufe über Engine-Versionen hinweg. Sie ist eine
**Analyse der Engine selbst**, nicht der Quellen.

### Was die Meta-Meta-Ebene zeigt

1. **Bestätigungs-Bias diagnostizierbar:** Die Engine
   *erkennt* ihren eigenen Bestätigungs-Bias in der Primäranalyse und
   *korrigiert* ihn in späteren Runs.

2. **Engine-Entwicklung sichtbar:** Frühe Runs diagnostizieren
   Bestätigungs-Bias, späte Runs falsifizieren die These aktiv.
   Das ist methodische Reife: von der Mustererkennung zur kritischen
   Selbstkorrektur.

3. **Agency-Stabilität:** Die Agency-Zuordnungen sind statistisch
   instabil. Die Adjudikation urteilt: Die Agency-Erklärung
   *HÄHLT NICHT STAND* auf Meta-Meta-Ebene — sie ist ein Engine-korrelierter
   Befund (nur in Runs mit Agency-Prompts sichtbar), kein Engine-unabhängiger
   Befund.

### Die zentrale Unterscheidung

| Ebene | Beobachtung (Transformation Früh → Spät) | Interpretation (Radikalisierung) | Agency-Erklärung |
|---|---|---|---|
| Meta-Ebene | HÄHLT STAND | HÄHLT NICHT STAND | Engine-korreliert |
| Meta-Meta-Ebene | HÄHLT STAND | HÄHLT NICHT STAND | Statistisch insignifikant |

- Die **Beobachtung** der Transformation hält auf beiden Ebenen stand.
- Die **Interpretation** als "Radikalisierung" wird auf beiden Ebenen widerlegt.
- Die **Agency-Erklärung** ist ein heuristisches Werkzeug, kein empirischer Befund.

## 12.4 Die FREIE FRAGE-Erkenntnis

Die FREIE FRAGE *„Sollten wir weniger von der Radikalisierung der Autoren
sprechen, dafür viel mehr von der Entfesselung der Sprache selbst?"*
lieferte eine entscheidende Reframierung:

> *„Die Synthese-Runs unterstützen die Ansicht, dass die Analyse sich auf
> die Entwicklung und Transformation der sprachlichen Operationen
> konzentrieren sollte, die eine eigene ‚Genealogie' oder ‚innere Logik'
> aufweisen. Sie raten explizit davon ab, persönliche Eigenschaften oder
> eine ‚Radikalisierung der Autoren' als Erklärungsmodell heranzuziehen."*

Das ist die **finale These** des Fallstudie-Papers: Nicht „Radikalisierung
der Autoren", sondern **„Genealogie sprachlicher Operationen"**.

## 12.5 Hermeneutischer Status der Agency-Zuordnung

Die Agency-Zuordnung ist eine **hermeneutische Interpretation**, kein
HRE-Messwert. HRE misst:
- syntaktische Desintegration (Satzlänge)
- lexikalische Reduktion (STTR)
- Enjambement-Verschiebung
- Heteroglossie

HRE misst **nicht** „Agency". Die Übersetzung dieser Messungen in
Agency-Qualitäten ist eine Interpretation, die explizit als solche
deklariert wird. HRE macht diese Interpretation *falsifizierbar* —
aber sie *beweist* sie nicht.

Diese Unterscheidung muss im Prompt selbst stehen, nicht nur in der
Dokumentation. Sonst verkauft die Engine Interpretation als Messung.

---

# 13. PERFORMANCE & GRENZEN

## 13.1 Metriken (v60, lokaler Betrieb)

| Metrik | Wert | Erklärung |
|---|---|---|
| Query-Zeit RAG (lokal, 9B) | 2–8 Minuten | LLM-Calls dominieren |
| Query-Zeit RAG (lokal, 27B) | 5–15 Minuten | Abhängig von VRAM/Quantisierung |
| STILISTIC LAB (6 Quellen) | 8–20 Minuten | Etappe 1 (~1 Min) + Etappe 2/3 (~10 Min) + Synthese (~5 Min) |
| Meta-Vollanalyse (8 Runs) | 15–40 Minuten | 7 Pipeline-Stufen mit je 1 LLM-Call |
| Meta-Meta-Analyse (15 Runs) | 30–60 Minuten | Sezieren + 5-Achsen-Vergleich |
| Embedding-Speed | ~500 Chunks/min | GPU empfohlen |
| Retrieval-Precision | 85–90% | Hybrid Search + VIP |
| Enforcer-False-Positives | <20% | Zwei-dimensionale Validierung |

**Warum so langsam?**
Das ist kein Bug, sondern ein bewusster Tradeoff. Jede Analyse durchläuft
mehrere LLM-Calls mit jeweils voller Attention. Die Engine ist für Tiefe
optimiert, nicht für Echtzeit. Die Falsifizierungs-Architektur (v60)
verdoppelt die Anzahl der LLM-Calls in der Meta-Ebene — aber das ist
der Preis für epistemische Redlichkeit.

## 13.2 Bekannte Grenzen

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

**5. Agency als heuristisches Werkzeug**
Die Agency-Qualitäten (intentional / responsiv / entbündelnd) sind
Interpretationen, keine Messwerte. Sie sind auf Meta-Ebene Engine-korreliert
(nur in Runs mit Agency-Prompts sichtbar) und auf Meta-Meta-Ebene statistisch
insignifikant. Wer Agency als Beweis verkauft, missversteht
die Architektur.

**6. Falsifizierung ≠ Beweis**
Die Falsifizierungs-Architektur kann die Ursprungs-These widerlegen —
sie *muss* es nicht. Wenn die These standhält, ist sie stärker abgesichert
als ohne Gegenprobe. Wenn sie fällt, ist das selbst ein Befund. Wer die
Falsifizierung als "Beweis der Widerlegung" verkauft, missversteht
die Methodik.

---

# 14. DEPLOYMENT

## 14.1 Lokaler Betrieb (Standard)

```bash
# Einmalige Einrichtung
cp .env.example .env
# LM Studio starten + Modell laden

# Starten
streamlit run app.py --server.port 8503
```

## 14.2 Cloud-Deployment (Optional)

Für Cloud Run oder ähnliche Dienste: `LLM_BACKEND=vertex` oder
`LLM_BACKEND=openai` in `.env` setzen und entsprechende Credentials
als Environment-Variablen konfigurieren. Siehe `.env.example`.

**Port-Konfiguration für Cloud Run:**
```
# Procfile
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

## 14.3 Troubleshooting

| Problem | Ursache | Lösung |
|---|---|---|
| "Connection refused" | LM Studio nicht aktiv | LM Studio starten + Server aktivieren |
| Leere Antworten | Modell nicht geladen | Modell in LM Studio auswählen |
| Sehr langsame Embedding | Kein GPU gefunden | Normales Verhalten; GPU installieren optional |
| "No chunks found" | Noch keine Imports | Import-Tab: Chat-Export hochladen |
| **v60:** "Agency: null" für alle Runs | Alte STILISTIC-LAB-Ergebnisse ohne Agency-Prompt | Mit v60-Prompts neu laufen lassen oder `null` als Befund akzeptieren |
| **v60:** Adjudikation "harmonisiert" statt zu bewerten | Prompt wurde verändert | Original-Prompt wiederherstellen — "Bewerte, was standhält, versöhne nicht" |
| **v60:** Homer/andere Beispiel-Autoren in Synthese | Stopword-Liste nicht geladen | `_AUTHOR_STOPWORDS` und `_ANALYSIS_TERM_STOPWORDS` prüfen |

---

# 15. ROADMAP

## Umgesetzte Meilensteine (v48 – v60)

- ✅ v48: Core RAG-Pipeline, Importer
- ✅ v49: Hybrid Search RRF, Hermeneutic Enforcer v1
- ✅ v50.5: VIP-Schutz, Essence Parity, Investigativ-Modus
- ✅ v50.7: Chronologische Synthese, logarithmische Chunks, Thread-Safety
- ✅ v50.9: ANALYTICAL_FORENSIC, Multi-Source-Enforcer, Public Launch
- ✅ v52: Local-First Release, `.env.example`, bereinigter Code
- ✅ v55: IFS-Supervisions-Panel
- ✅ v56: Drei-Phasen-Synthese, Pro-Quelle-Extraktion (Planung)
- ✅ v57: STILISTIC Mode (drei Etappen, Pro-Quelle-Extraktion, Verify-Gate)
- ✅ v58: Tynjanow-Integration, Modus-Erkennung, Verdichtungsschicht
- ✅ v59: META-VERGLEICH (5-Achsen-Protokoll)
- ✅ v60: Falsifizierungs-Architektur (Agency, Gegenposition, Adjudikation, revidierte Destillation, Meta-Meta)

---

# 16. ANHÄNGE

## 16.1 Credits

**Project Lead:** Grigori Pantijelew (Landesinstitut für Schule Bremen)

**KI-Entwicklungs-Team:**
- **Claude Sonnet 4.6 (Anthropic):** Architektur-Konzepte, Design-Patterns, Code-Review, Methodische Beratung zur Falsifizierungs-Architektur
- **Gemini (Google):** Code-Implementierung, SDK-Migration, Debugging
- GLM: Code-Implementierung
- **Kimi (Moonshot AI):** Lektorat aller Texte und Dokumentation

**Infrastruktur:** Google Cloud Platform (Research Credits Program)

## 16.2 Glossar

| Begriff | Bedeutung |
|---|---|
| **Adjudikation** | [v60] Bewertungs-Schritt zwischen Bestätigung und Gegenposition; keine Harmonisierung |
| **Agency-Qualität** | [v60] Hermeneutische Interpretation der Steuerungsform: intentional / responsiv / entbündelnd |
| **BEOBACHTEN** | [v60] Strang A — bestätigende Meta-Analyse |
| **Chunk** | Textsegment (typisch 300–500 Tokens), atomare Indexierungseinheit |
| **Dominante** | [v57/v58] Tynjanow-Konzept: "Was hält den Text zusammen?" |
| **Enjambement** | Zeilenumbruch mitten in einem Satz — Indikator für syntaktische Isolierung |
| **Essence Parity** | Logarithmische Fairness-Quota pro Dokument |
| **Falsifizierungs-Architektur** | [v60] Vier-Schritt-Gegenprobe, die die Primäranthese herausfordert |
| **FREIE FRAGE** | [v60] Gezielte Frage zu SEZIEREN-Daten — Option B1 (schnell) oder B2 (VOLLANALYSE) |
| **GEGENPOSITION** | [v60] Strang B — falsifizierende Meta-Analyse |
| **Gini-Koeffizient** | Maß für Ungleichheit (0 = perfekt fair, 1 = maximal unfair) |
| **Grundoperation** | [v58] Tynjanow-Konzept: Was der Text TUT, nicht was er VERWENDET |
| **Hermeneutic Enforcer** | Zwei-dimensionaler Validierungs-Kern |
| **Hermeneutic Router** | Intent-Klassifizierungs-Modul |
| **Hotspot-Satz** | [v57] Längster / kürzester / inhaltlich dichtester Satz eines Textes |
| **Investigativ-Modus** | Retrieval-Strategie für kleine Korpora (≤5 Dokumente) |
| **Modus** | [v58] Vorentscheidung vor der Analyse: Polemik / Beschwörung / Nachdenken / Erzählen / Spiel |
| **Meta-Meta-Ebene** | [v60] Analyse der Engine selbst über mehrere Meta-Läufe hinweg |
| **META-VERGLEICH** | [v59] Werkzeugvergleich zweier Analysen, 5-Achsen-Protokoll |
| **Pro-Quelle-Extraktion** | [v57] Eine LLM-Call pro Quelle statt Monolith-Call |
| **revidierte Destillation** | [v60] Synthetisiert nur, was der Gegenprobe standhält |
| **RRF** | Reciprocal Rank Fusion — Algorithmus zur Ranking-Kombination |
| **Rescue Mission** | Fallback-Mechanismus bei 0 Chunks nach Reranking |
| **SEZIEREN** | [v57] Etappe 1 — 100% Python, 0% LLM |
| **STIL-TITEL** | [v57] Etappe-2-Output: "Der TITEL dieses Stils" |
| **STTR** | Standardized Type-Token Ratio — Textlängen-korrigierte lexikalische Vielfalt |
| **TTR** | Type-Token Ratio — rohe lexikalische Vielfalt (durch Textlänge verzerrt) |
| **Tynjanow-Integration** | [v58] Analytisches Rahmen nach Jurij Tynjanow: Dominante + Grundoperation |
| **Verify-Gate** | [v57] Substring-Existenz-Prüfung vor Synthese — verhindert halluzinierte Zitate |
| **VIP-Schutz** | Garantiert top-3 Chunks pro ausgewähltem Dokument |
| **VOLLANALYSE** | [v60] Meta-Modus mit allen 7 Pipeline-Stufen inkl. Falsifizierung |
| **2D-Framework** | [v60] Forschungsplanungs-Raster: Modus × Agency-Qualität (3+3 Felder) |

## 16.3 Kontakt

**Projekt-Lead:** Grigori Pantijelew
**Email:** hermeneutic-engine@proton.me
**Repository:** https://github.com/gpantijelew/hermeneutic-engine
**Preprint:** https://doi.org/10.5281/zenodo.18774828

---

**Ende der FIBEL v60**
*Stand: Juli 2026 | Lizenz: MIT*
