# Changelog — Hermeneutic Reconstruction Engine

All significant changes to this project are documented here.

---

## [v60] - 2026-07-01
### Highlights
- **Falsifizierungs-Architektur:** Die Meta-Ebene wird um eine vier-Schritt-Gegenprobe erweitert, die die bestätigende Pipeline (Strang A) systematisch herausfordert. Die Engine kann nun ihre eigene Ausgangshypothese widerlegen — und tut es in den durchgeführten Testläufen auch.
- **Agency-Extraktion (Schritt 1):** Pro Meta-Run wird die Agency-Qualität (intentional / responsiv / entbündelnd) über ein kontrolliertes Mini-LLM extrahiert. Agency-Qualitäten sind kontrollierte Vokabular-Werte, keine freien Substantiv-Phrasen — damit aggregierbar, aber explizit als *hermeneutische Interpretation* gekennzeichnet, nicht als HRE-Messwert.
- **Quellen-Gegenposition (Schritt 2, dormant):** Die STILISTIC-LAB-Pipeline erhält einen schlafenden Strang-B-Eingang, der auf Etappe-1-Daten eine Gegenposition zur Primäranthese formulieren kann. Wird nicht automatisch getriggert, sondern über Freie Frage (Option B) verfügbar.
- **Meta-Gegenposition (Schritt 3):** META-GEGENPOSITION als eigener Intent in `hermeneutic_protocol.yaml`. Argumentiert auf Meta-Ebene GEGEN die These der bestätigenden Pipeline. Bekommt nur die Fragestellung der Quellen-Gegenposition als Kontext, nicht deren Antworten — vermeidet Bestätigungsdruck.
- **Meta-Adjudikation (Schritt 4):** META-ADJUDIKATION als eigener Intent. Bewertet, was von Bestätigung (A) und Gegenposition (B) standhält und was nicht. KEINE Harmonisierung — Spannung bleibt bestehen. Input: beide rohen Ströme, gleichwertig.
- **Revidierte Destillation:** Die abschließende META-DESTILLATION wird revidiert — synthetisiert nur, was der Gegenprobe standhält. Die Ursprungs-These kann durch diese Destillation modifiziert oder widerlegt werden.
- **Freie Frage (Option B — VOLLANALYSE):** Die Freie-Frage-Funktion kann nun entweder nur SEZIEREN + FREIE FRAGE ausführen (schnell) oder im VOLLANALYSE-Modus alle Stränge inklusive Adjudikation durchlaufen und dann die Freie Frage auf die adjudizierten Daten anwenden.
- **2D-Framework (Modus × Agency-Qualität):** Forschungsplanungs-Raster mit 3 besetzten Feldern (Entstehung/intentional, Transformation/responsiv, Enthüllung/entbündelnd) und 3 leeren Feldern als explizite Forschungslücken.
- **Meta-Meta-Ebene:** Vergleich von 15 Meta-Läufen über Engine-Versionen hinweg. Diagnostiziert Bestätigungs-Bias, Engine-Entwicklung (Mustererkennung → kritische Selbstkorrektur) und Agency-Stabilität.

### Technical
- `meta_hermeneutic_engine.py`: Neue Funktionen `extract_agency_per_run()`, `meta_gegenposition()`, `meta_adjudikation()`, `meta_destillation_revidiert()` sowie Header-Parser `_extract_meta_header()` und `_detect_mode()` (VOLLANALYSE vs. FREIE FRAGE)
- `stilistic_lab_pipeline.py`: Neue Stopword-Listen `_AUTHOR_STOPWORDS` (Homer, Homeros, Homers, etc.) und `_ANALYSIS_TERM_STOPWORDS` (27 analytische Begriffe: Agency, Adjudikation, Gegenposition, Bestätigung, etc.) zur Verhinderung von Kontext-Pollution in Synthesen
- `hermeneutic_protocol.yaml`: Vier neue Intents — META_GEGENPOSITION, META_ADJUDIKATION, META_DESTILLATION (revidiert), FREIE_FRAGE — jeweils mit system_instruction und mode_instruction
- `text_analyzer.py`: Modus-Erkennung (Polemik, Beschwörung, Nachdenken, Erzählen, Spiel) als Vorentscheidung; Verdichtungsschicht (Regex-Extraktion von Dominante, Grundoperation, Modus, Stil-Titel)
- `destillation_tab.py`: Radio-Option `freie_frage_option_b` für VOLLANALYSE-Modus; Anzeige aller 7 Pipeline-Stufen mit Stufen-Dauer

### Fixes
- **Homer-Pollution:** Auto-Loader lädt jetzt nur Markdown-Dateien aus demselben Verzeichnis, und die Prompts wurden generalisiert — kein "Homer als Beispiel-Autor" mehr in User-sichtbaren Prompts
- **Author-Deduplizierung:** Canonical-Name-Normalisierung verhindert, dass derselbe Autor unter verschiedenen Schreibweisen (Puschkin/Pushkin/Puškin) als unterschiedliche Akteure gezählt wird
- **Kernhypothese-Parser:** Doppeltitel-Struktur (H2 + H3 auf derselben Zeile) wird korrekt aufgelöst; `extract_kernhypothese` liefert keine leeren Treffer mehr
- **Sprachregister in Destillation:** Etappe-1 Sektion 8 (Sprachregister-Analyse) wird korrekt in die revidierte Destillation propagiert
- **BEOBACHTEN-Prompt:** Hinweis auf die existence der Gegenposition hinzugefügt — der bestätigende Strang weiß, dass er herausgefordert wird, ohne die Gegenposition zu sehen
- **STOPWORDS:** 27 analytische Begriffe (Agency, Adjudikation, etc.) werden aus Top-Wort-Statistiken herausgefiltert — verhindert Selbstreferenz der Engine in Synthesen
- **Stufen-Dauer:** Alle 7 Pipeline-Stufen werden mit Dauer angezeigt (vorher nur 5)

### Gelernte Lektionen
- **Falsifizierung als architektonisches Prinzip:** Eine Pipeline, die ihre eigene Ausgangshypothese widerlegen kann, ist epistemisch stärker als eine, die nur bestätigt. Die Engine widerlegt in den Testläufen die "Radikalisierung"-These für alle drei Fälle (Puschkin, Blok, Brodsky) — nicht durch externen Eingriff, sondern durch ihre eigene Gegenprobe.
- **Agency als hermeneutische Kategorie:** Agency-Zuordnungen sind Interpretationen, keine Messwerte. Sie sind auf Meta-Ebene Engine-korreliert (nur in Runs mit Agency-Prompts sichtbar) und auf Meta-Meta-Ebene statistisch insignifikant (1–2 von 15 Runs). Die Agency-Kategorie ist ein heuristisches Werkzeug, kein empirischer Befund — diese Unterscheidung muss im Prompt selbst deklariert werden, nicht nur in der Dokumentation.
- **Bestätigungs-Bias ist diagnostizierbar:** 13 von 15 Meta-Läufen diagnostizieren einen Bestätigungs-Bias in der Primäranalyse. Die Engine *erkennt* diesen Bias und *korrigiert* ihn in späteren Runs — das ist die methodische Reife, die das System trägt.
- **Anti-Harmonisierung ist technisch:** Adjudikation darf nicht "versöhnen" — Spannung muss erhalten bleiben. Diese Regel muss im Prompt explizit stehen, sonst tendiert das LLM zur Synthese.

### Migration Guide
1. Keine Breaking Changes für bestehende STILISTIC-LAB-Analysen
2. Bestehende Meta-Analysen ohne Agency-Information laufen weiter — Agency-Extraktion gibt `null` zurück, was selbst ein Befund ist ("diese Runs kennen die Agency-Kategorien nicht")
3. Für die Falsifizierungs-Architektur muss `hermeneutic_protocol.yaml` um die vier neuen Intents ergänzt werden (Migrationsskript folgt mit Release-Paket)
4. `destillation_tab.py` muss um die Radio-Option `freie_frage_option_b` ergänzt werden

---

## [v59] - 2026-05-30
### Highlights
- **META-VERGLEICH:** Neuer Destillations-Modus zum Vergleich zweier analytischer Verfahren auf Methode und Leistung. 5-Achsen-Protokoll: Konvergenzen, Divergenzen, Komplementarität, Grenzen, Systematischer Ertrag. Architektur: Einzel-LLM-Call (Inputs = bereits Analysen, keine Pipeline). UI: Zwei-Seiten-Eingabe mit editierbaren Labels, DB-Quellen oder Freitext, optionale Forschungsfrage.
- **Architektur-Entscheidung:** META-VERGLEICH ist keine Pipeline — Inputs sind bereits Analysen, keine Primärquellen. Kein Etappe 1, keine pro-Quelle-Analyse.
- **Anti-Harmonisierung:** Werkzeugvergleich, nicht Rangierung — keine synthetisierende Synthese am Ende.

### Technical
- `destillation_tab.py`: Neue Radio-Option `meta_vergleich` + `_render_meta_vergleich_ui()` mit zwei-Seiten-UI
- `stilistic_lab_pipeline.py`: Neue Funktionen `run_meta_vergleich()` + `_build_meta_vergleich_prompt()` + `format_meta_vergleich_as_markdown()`
- `hermeneutic_protocol.yaml`: Neuer `META_VERGLEICH` Intent (system_instruction + mode_instruction)
- `config.py`: ENGINE_VERSION v59

---

## [v58] - 2026-05-27
### Highlights
- **STILISTIC Mode v57.7.2 bestätigt als v58:** Vier-Sektionen-Format getestet und validiert. Drei erfolgreiche Tests (Fet/Blok, Herzen/Lenin).
- **Patch v584 — Dominanten-Schärfung:** Sekundärfrage "Mittel vs. Werkzeug" — zwingt das Modell, Oberflächliches von Strukturellem zu unterscheiden. Beispiel: "Eine Antithese ist oft Werkzeug einer Dominante, nicht die Dominante selbst."
- **Patch v585 — Tynjanow-Integration:** GRUNDOPERATION als zweite Analyseachse (Operation vs. Figur), FREIER RAUM als optionale Meta-Ebene, OPERATIONS-GENEALOGIE in der Synthese. Klärungsbeispiel: "Der Text stellt X und Y gegenüber" beschreibt Struktur. "Der Text zerstört X durch die Berührung mit Y" beschreibt Operation.
- **Patch v586 — Relationale Pipeline & Modus-Erkennung:** Sieben Eingriffe für den Übergang von atomistischer zu relationaler Beobachtung. Modus-Erkennung als Vorentscheidung vor der Analyse (Polemik, Beschwörung, Nachdenken, Erzählen, Spiel). Hypothese-erst-Logik in der Synthese: Falsifizierbare Hypothese vorab, dann Beweisführung. Verdichtungsschicht als Informationsarchitektur (48 Wörter Konzentrat vor 4000 Wörter Volltext).

### Technical
- `stilistic_lab_pipeline.py`: Prompt-Struktur Etappe 2+3 umgeschrieben (6→5 Sektionen: Dominante, Grundoperation, Beobachtung, Vertiefung, Stil-Titel); Synthese umgeschrieben (7→5 Sektionen: Hypothese, Beweisführung, Kennzahlen-Überraschung, Freier Raum, Fazit)
- `text_analyzer.py`: Modus-Erkennung hinzugefügt; Verdichtungsschicht (Regex-Extraktion von Dominante, Grundoperation, Modus, Stil-Titel pro Quelle)
- Deadlock-Fix: `threading.Lock()` → `RLock()`, `delete_chat()` umstrukturiert

### Gelernte Lektionen
- **Operation vs. Figur:** Die Pipeline sah Figuren, weil ihr Vokabular aus der Rhetorik kam. Tynjanow sieht Operationen, weil er fragt, was der Text TUT, nicht was er VERWENDET.
- **Horizont vs. Instruktion:** "Du weißt, in welchem Vergleich dieser Text steht" setzt die epistemische Haltung. "Vergleiche diesen Text mit den anderen" erzwingt das Output-Format. Horizont funktioniert besser.
- **Hypothese-erst-Logik:** Wenn das Modell die Hypothese vorab formulieren muss, entsteht intellektuelle Spannung. Die Falsifizierbarkeitsfrage ist das stärkste Gegenmittel gegen vage Generalaussagen.

---

## [v57] - 2026-05-19
### Highlights
- **STILISTIC Mode:** Neuer Analysemodus für stilistischen Vergleich. Drei-Etappen-Architektur: Etappe 1 (SEZIEREN — 100% Python, 0% LLM: Satzbau, TTR, Morphologie, Hotspot-Sätze) → Etappe 2 (EINORDNEN — LLM interpretiert Python-Daten, 2-3 Beobachtungen mit Zitat-Beleg) → Etappe 3 (FREIER RAUM — LLM macht kreativen Sprung).
- **Kernprinzip:** Python zählt, LLM charakterisiert — aber auf Faktenbasis, nicht auf Intuition.
- **Pro-Quelle-Extraktion + Verify-Gate:** 6×5K Calls statt 1×28K Monolith — volle Attention pro Dokument, garantiert ≥2 Zitate/Quelle. Verify-Gate: Substring-Existenz-Prüfung vor Synthese.
- **Vier-Sektionen-Reform (v57.7.1):** Struktureller Umbau des Analyse-Prompts: (1) DIE DOMINANTE — "Was hält den Rest zusammen", (2) BEOBACHTUNG — Fließ-Anweisung statt Formular, (3) VERTIEFUNG — "Was wird erst sichtbar, wenn man die Dominante wegdenkt?", (4) STIL-TITEL — "Schreibe den TITEL dieses Stils".
- **Sprach-Audit (v57.7.2):** 11 Sprach-Korrekturen im Prompt (Anglicismen, falsche Präpositionen, Terminologie). Parataktischer Stil als Stärke bestätigt.

### Technical
- `text_analyzer.py` (~869 Zeilen): Deterministische Textstatistiken — Satzstatistiken (HS/NS, Ø/Median/Max-Satzlänge), Satzzeichen-Verteilung, Type-Token-Ratio, Top-Wörter, Bigramme/Trigramme, morphologische Komplexität pro Satz, Hotspot-Sätze
- `stilistic_lab_pipeline.py` (~655 Zeilen): Etappe 2+3 Prompt + Globale Synthese
- `citation_rag.py`: Pro-Quelle-Extraktion + Verify-Gate
- `hermeneutic_protocol.yaml`: STILISTIC-Intent mit eigener compact_instruction
- `hermeneutic_router.py`: STILISTIC als fünfter Intent

---

## [v56] - 2026-05-16
### Highlights
- **Drei-Phasen-Synthese:** Phase 1 (Draft) → Phase 2 (Mechanischer Check: C1-C6) → Phase 3 (Gezielte Korrektur, temp=0.0, flash). Nur bei Fehlern wird korrigiert — deterministisch, nicht probabilistisch.
- **Pro-Quelle-Extraktion (geplant):** 6×5K Calls statt 1×28K Monolith — volle Attention pro Dokument, garantiert ≥2 Zitate/Quelle.
- **Titel-Mapping-Injektion (Fix J.2):** QUELLEN-VERZEICHNIS direkt vor AUFGABE — löst "Dokument"-Platzhalter-Problem.
- **Paraphrase-Ausweg (Fix J.3):** "Präziser Verweis OHNE Zitat ist besser als erfundenes Zitat" — reduziert Zitat-Fabrikation.
- **Extraction-Modell (Fix J.1):** flash-lite → flash für buchstabengetreues Kopieren.
- **Bekannte Limitation:** Quote-Extraktion bei >20K Token unterversorgt (Attention-Verlust). Fix geplant: Pro-Quelle-Extraktion.

---

## [v55] - 2026-05-08
### Highlights
- Mission D: Neues IFS-Supervisions-Panel integriert (Map-Reduce-Pipeline mit SUPERVISION_MANAGER, SUPERVISION_EXILE und SUPERVISION_META Agenten für psycho-algorithmische Resilienz-Schulung).

---

## [52.0] - 2026 — "Local-First Public Release"

### Summary
First public release optimised for local deployment. The engine now runs
out of the box with LM Studio and open-weight models — no API key required.
Vertex AI and OpenAI-compatible cloud backends remain available as opt-in.

### Changes

#### Default Configuration
- Backend default changed to LM Studio (port 1234, LM Studio standard)
- Default model: `qwen3.5-9b-highiq-instruct`
- Added `.env.example` for clean first-time setup

#### Architecture
- `config.py`: Port default 8888 → 1234; removed temporary debug prints
- `llm_wrapper.py`: Vertex AI backend retained as opt-in; internal cleanup
- All modules: v52 header updates

#### Documentation
- README rewritten for public audience (Quickstart, feature overview, architecture diagram)
- FIBEL updated: local-stack focus, Essence Parity section expanded,
  cloud-specific references moved to optional sections
- CHANGELOG scrubbed of internal workflow references

---

## [50.9] - 2026 — "Public Launch"

### New Features

- **ANALYTICAL_FORENSIC intent:** Fourth query type for deconstruction,
  motive analysis, critical counter-reading
- **Dynamic system instructions:** Four intent-specific LLM personas
  replace the universal system prompt
- **Intent propagation:** Router decision now flows through the entire
  reranker stack
- **Multi-source validation:** Hermeneutic Enforcer now handles sentences
  citing multiple sources simultaneously
- **Markdown import:** `.md` / `.markdown` format support added
- **Forensic header whitelist:** Post-processing preserves structured
  forensic output headers

### Technical
- Router context fix for the analysis window (was silently using stale context)
- Temperature split: `ANALYTICAL_FORENSIC` synthesis uses 0.4,
  all other intents use 0.7

---

## [50.8] - 2026 — "Stabilization"

- Cloud Run deployment hardening (dynamic port binding, keep-alive mechanism)
- Chat export as Markdown download
- Emergency intervention UI for corrupted session state recovery
- Iterative debugging of local vs. cloud deployment differences

---

## [50.7] - 2026 — "Architectural Maturation"

### Major Changes

**SDK Migration**
Complete migration to `google.genai` v1.0 (from deprecated `google.generativeai` v0.x).
Affects: `app.py`, `vector_store.py`, `citation_rag.py`, `hermeneutic_enforcer.py`, `config.py`.

**Chronological Synthesis**
Chunks are now sorted by date extracted from metadata before synthesis.
Enables temporal reconstruction of how thoughts develop over time.

**Thread-Safety: BM25 Cache**
BM25 index wrapped in `threading.Lock` singleton — prevents race conditions
in multi-user environments.

**Two-Dimensional Enforcer**
Claims validated across two independent axes:
- Hermeneutic dimension: How is it said? (Quote, Paraphrase, Inference)
- Validity dimension: Is it correct? (Supported, Contradiction, Unsupported)

**Rescue Mission**
Fallback cache (`_original_results_cache`) restores chunks from
user-selected documents that were eliminated during reranking.

**Logarithmic Chunk Scaling**
Old hard cap (12 chunks/doc) replaced by bio-inspired logarithmic formula.
Chunk budget scales with document length — short texts get proportionally
fair representation without being drowned by large corpora.

**Central Logging**
`RotatingFileHandler` (max 5 MB) with suppression of verbose third-party
library output.

---

## [50.6] - 2025-12 — "Memory Precision"

- Importer improvements: DeepSeek, Grok, Perplexity, Gemini HTML parsers
  made more robust against inconsistent export structures
- Diagnostic tools for chunk quality inspection (`modules/utils/`)
- Extended chunk classification (`chunk_classifier.py`)

---

## [50.5] - 2025-12 — "Hermeneutic Fairness"

### Mission
Guarantee that every user-selected source appears in synthesis —
regardless of language, length, or embedding quality.

### Core Features

**Hermeneutic Router**
Flash-Lite model classifies query intent automatically.
Intent types: `LITERARY`, `FACTUAL`, `ANALYTICAL`.
Dynamically adjusts retrieval limit (k: 15–50) and reranker threshold (0.45–0.7).

**Investigativ-Modus**
Triggered for ≤5 selected documents. Directly loads selected documents
into RAM (skipping global vector index), enforces fairness quota
(min. 20 chunks/document).

**VIP Protection (RRF Fusion)**
Guarantees top-3 chunks from every selected document before reranking.
Prevents reranker from eliminating sources entirely.

**Essence Parity**
Caps chunks per document + enforces citation quota in synthesis prompt
(3–4 citations per source regardless of chunk count).

**Multilingual Query Expansion**
Automatic translation: DE → EN, FR, RU.
Cross-lingual similarity improvement: 0.42 → 0.65 (+55%).

### Performance (5 documents, 4 languages)

| Metric | v49 Baseline | v50.5 | Change |
|---|---|---|---|
| Source coverage | 40% (2/5) | 100% (5/5) | +150% |
| Gini coefficient | 0.68 | 0.42 | -38% |
| Context distribution | 86/5/5/3/0% | 41/35/10/10/3% | Balanced |
| Query time | ~8s | ~9s | +12% |

---

## [49.0] - 2025-12 — "The Hermeneutic Triad"

- Hybrid Search (Vector + BM25) with Reciprocal Rank Fusion
- Chronological speaker-block grouping
- Hermeneutic Enforcer v1 with parallel validation
- Cross-encoder reranking

**Known issues:** Multilingual bias (DE query → DE sources preferred);
reranker could eliminate small documents entirely (fixed in v50.5).

---

## [48.0] - 2025-12 — "Initial Release"

- Core RAG pipeline
- ChromaDB vector store + sentence-transformers embeddings
- SQLite database with FTS5 full-text search
- Google Embedding API integration
- HTML chat importers (DeepSeek, ChatGPT, Claude, Gemini, Kimi, Grok)
