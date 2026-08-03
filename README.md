# Hermeneutic Reconstruction Engine (HRE)

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Version](https://img.shields.io/badge/version-v61-green.svg)](CHANGELOG.md)
[![Status](https://img.shields.io/badge/status-production%20ready-brightgreen.svg)]()
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18774828.svg)](https://doi.org/10.5281/zenodo.18774828)
[![YouTube](https://img.shields.io/badge/YouTube-Case_Study-red?logo=youtube)](https://youtu.be/HveLGOuWJM0)

**Full Name:** Hermeneutic Reconstruction Engine for Archaeology of Mind
**Focus:** Source Parity, Deep Validation & Chronological Synthesis for Multilingual Text Analysis
**Stack:** Python, Streamlit, SQLite, ChromaDB, LM Studio (lokal), Vertex AI (Gemini)

Lokales Forschungswerkzeug für die Diskursarchäologie von KI-Gesprächen — mit hermeneutischer Validierung, Zitatnachweisen, Faktvalidierung, Meta-Analyse, Drei-Phasen-Synthese (Draft → Mechanischer Check → Korrektur), stilistischer Analyse (STILISTIC Mode), Meta-Vergleich analytischer Verfahren (META-VERGLEICH) und einem IFS-Trostbau-Modul für persönliche Reflexion (v61).

---

## Was ist die HRE?

Die HRE ist eine **lokale, privat betriebene** Anwendung, die es ermöglicht:

- **KI-Gespräche zu importieren** (ChatGPT, Claude, Gemini, Kimi, DeepSeek, Grok, Perplexity, LM Arena, Hotbot, GLM, Wikisource, PDF, EPUB, FB2, Markdown)
- **Diskursarchäologie zu betreiben** — mit hermeneutischer Analyse, Zitatnachweisen und Faktvalidierung
- **Stilanalyse durchzuführen** — mit dem STILISTIC Mode (Drei-Etappen-Architektur: Python-Statistiken → LLM-Beobachtung → Kreativer Sprung)
- **Analytische Verfahren zu vergleichen** — mit META-VERGLEICH (5-Achsen-Vergleich: Konvergenzen, Divergenzen, Komplementarität, Grenzen, Systematischer Ertrag)
- **Forschung zu dokumentieren** — mit reproduzierbaren Analysen, Quellenangaben und einem Critical Apparatus
- **Persönliche Reflexion zu unterstützen** — über den IFS-Trostbau (Internal Family Systems), mit mode-abhängigen Krisenschwellen, Echo-Wächter und Anker-Modus (v61)

Alle Daten bleiben lokal. Keine Cloud-Abhängigkeit, kein API-Key erforderlich.

---

## Schnellstart

### Voraussetzungen

Damit die HRE auf deinem Computer läuft, brauchst du:

- **Python 3.11 oder neuer** — [hier herunterladen](https://www.python.org/downloads/). Wähle bei der Installation unter Windows die Option „Add Python to PATH".
- **LM Studio** — ein kostenloses Programm, das lokale KI-Modelle auf deinem Rechner ausführt. [Hier herunterladen](https://lmstudio.ai/). Es läuft auf Windows, macOS und Linux.
- **Arbeitsspeicher (RAM):** mindestens 8 GB, besser 16 GB für komfortables Arbeiten.
- **Grafikkarte (optional, aber empfohlen):** Mind. 6 GB VRAM für flüssiges Arbeiten mit dem 9B-Standardmodell.
- **Betriebssystem:** Windows, macOS oder Linux.

### Installation — Schritt für Schritt

**1. Repository herunterladen**

Öffne ein Terminal (unter Windows: PowerShell) und gib ein:

```bash
git clone https://github.com/gpantijelew/hermeneutic-engine.git
cd hermeneutic-engine
```

Falls du `git` nicht installiert hast: Du kannst das Repository auch als ZIP-Datei über den grünen „Code"-Button auf der GitHub-Seite herunterladen und entpacken.

**2. Virtuelle Python-Umgebung einrichten**

Das hält die Abhängigkeiten der HRE sauber von anderen Python-Projekten auf deinem Rechner:

```bash
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate
```

Du erkennst, dass die Umgebung aktiv ist, wenn im Terminal `(venv)` vor dem Prompt steht.

**3. Abhängigkeiten installieren**

```bash
pip install -r requirements.txt
```

Das lädt alle benötigten Bibliotheken (Streamlit, ChromaDB, BeautifulSoup u. a.). Beim ersten Mal dauert das einige Minuten.

**4. LM Studio einrichten**

1. LM Studio öffnen.
2. Im Reiter „Search" ein Modell suchen und herunterladen. Empfohlen für den Anfang: `qwen3.5-9b-highiq-instruct` (gründlich, läuft auf den meisten Rechnern).
3. Zum Reiter „Developer" wechseln und den lokalen Server starten. Standard-Port: `1234`. LM Studio muss im Hintergrund weiterlaufen, solange du die HRE nutzt.

**5. Konfigurationsdatei anlegen**

Kopiere die Vorlage `.env.example` zu `.env` (die Datei ist meist schon passend eingestellt):

```bash
cp .env.example .env
```

Falls du ein anderes Modell oder einen anderen Port verwenden willst, öffne `.env` in einem Texteditor und passe die Werte an.

**6. Anwendung starten**

```bash
streamlit run app.py
```

Dein Browser öffnet sich automatisch unter `http://localhost:8501`. Falls nicht, öffne die Adresse manuell.

### Erste Schritte in der App

1. **Import:** Lade eine Chat-Export-Datei hoch (z. B. HTML-Export von ChatGPT/Claude/DeepSeek) oder einen literarischen Text (TXT, MD, PDF, EPUB, FB2).
2. **Analyse:** Wähle im Analyse-Tab deine Quellen aus und stelle eine Frage — auf Deutsch oder Englisch.
3. **Tiefenprüfung (optional):** Klappe „Enforcer Protokoll" auf und klicke „Tiefenprüfung starten". Jede Aussage wird dann gegen die Quellen validiert.

---

## Architektur

```
HRE/
├── app.py                    # Einstiegspunkt (Streamlit), Tab-Orchestrierung, Auth
├── modules/                  # Kernmodule
│   ├── llm_wrapper.py        # LLM-Call-Varianten (LM Studio / OpenAI / Vertex), Retry-Logic
│   ├── database.py           # SQLite CRUD, FTS5, Chunk-Registry, Analyses, Enforcer-Reviews
│   ├── vector_store.py       # ChromaDB + BM25 Hybrid Search, SQLite Vector Store
│   ├── citation_rag.py       # CitationRAG mit Rescue Mission & Essence Parity
│   ├── hermeneutic_router.py # Intent-Routing (FORENSIC / EXEGESIS / SYNTHESIS / META_ANALYTICAL / STILISTIC)
│   ├── hermeneutic_reranker.py # LLM-basiertes Re-Ranking
│   ├── hermeneutic_enforcer.py # Faktvalidierung, Confidence-Scoring, Sampling
│   ├── prompt_manager.py     # YAML-zentralisierte Prompts
│   ├── text_analyzer.py      # Etappe 1: Deterministische Textstatistiken (Satzbau, TTR, Morphologie)
│   ├── stilistic_lab_pipeline.py # Etappe 2+3: STILISTIC Analyse + Globale Synthese + META-VERGLEICH
│   ├── meta_hermeneutic_engine.py # Meta-Engine + Falsifizierungs-Architektur (Agency, Gegenposition, Adjudikation)
│   ├── ifs_engine.py         # IFS Trostbau (v61): PromptManager + llm_call + Mode-Wrapper
│   ├── echo_guard.py         # IFS Trostbau (v61): Wortüberlappungs-Prüfung, einmalige Neugenerierung
│   ├── anker_loader.py       # IFS Trostbau (v61): Lädt Anker-Liste als hermeneutisches Protokoll
│   ├── emergency_interceptor.py # IFS Trostbau (v61): Mode-abhängige Krisenschwellen (IFS_FIGHT=2, IFS_CONTROL=3, IFS_FEAR=2, NAMASTE=2)
│   ├── embedding_cache.py    # Embedding-Hash-Cache (SQLite), SHA-256, Batch-Commits
│   ├── health_monitor.py     # SystemHealthMonitor, CPU/Memory/Disk/GC-Metriken
│   ├── export.py             # Markdown-Export, Reproducibility Manifest
│   ├── importers/            # 20+ Plattform-Importer, Auto-Detektor
│   └── config.py             # DB-Pfade, Model-Name, Domain-Profile
├── ui/                       # Streamlit-UI-Module
│   ├── chat_tab.py           # Chat-Interface
│   ├── analysis_tab.py       # Hermeneutische Analyse
│   ├── destillation_tab.py   # Best-of-Synthese, STILISTIC & META-VERGLEICH
│   ├── stilisierung_tab.py   # Text-Veredelung (Agentic Loop: Drafter/Critic/Editor)
│   ├── ifs_tab.py            # IFS Trostbau UI (v61: Triad + Single-Modus, Mode-Labels)
│   ├── meta_hermeneutic_tab.py # Meta-Engine UI (Falsifizierungs-Architektur)
│   ├── system_health_tab.py  # Health-Dashboard, Confidence Calibration, Corpus Stats
│   ├── qa_review_tab.py      # QA-Review-Queue, Enforcer-Sampling
│   ├── chat_list.py          # Sidebar: Chat-Liste mit FTS5-Suche, Lazy-Load
│   ├── settings_panel.py     # Einstellungen
│   ├── state.py              # Zentrales State-Management
│   └── components.py         # Wiederverwendbare UI-Bausteine
├── tests/                    # pytest-Suite
├── hermeneutic_protocol.yaml # Zentrale Prompt-Regeln (IFS-spezifische Regeln seit v61)
└── AGENTS.md                 # Projekt-Plan & Qualitätsbewertung
```

### Datenfluss

1. **Import:** HTML/JSON/PDF/EPUB → Importer → SQLite (Chats) + ChromaDB (Vektoren)
2. **Chat:** Streamlit UI → `llm_wrapper.py` → LM Studio / OpenAI / Vertex
3. **Analyse:** Query → `hermeneutic_router.py` → BM25 + Vectors → `citation_rag.py` → Synthese
4. **STILISTIC:** Text → `text_analyzer.py` (Python-Statistiken) → `stilistic_lab_pipeline.py` (LLM-Beobachtung + Synthese)
5. **META-VERGLEICH:** Zwei Analysen → `stilistic_lab_pipeline.py` → 5-Achsen-Vergleich
6. **IFS Trostbau:** Situation → `ifs_engine.py` (Mode-Wrapper) → LLM mit modus-spezifischem Krisen-Threshold (`emergency_interceptor.py`) → Echo-Prüfung (`echo_guard.py`) → Anker-Protokoll (`anker_loader.py`)

---

## Konfiguration

### `.env` (optional)

```env
# Passwort für die App (optional, für lokale Entwicklung)
HRE_PASSWORD=dein-passwort

# OpenAI API-Key (falls LLM_BACKEND=openai)
OPENAI_API_KEY=sk-...

# Vertex AI (falls LLM_BACKEND=vertex)
GOOGLE_PROJECT_ID=dein-projekt
```

### `modules/config.py`

Zentrale Konfiguration:
- `LM_STUDIO_URL` (Standard: `http://localhost:1234/v1`)
- `LLM_BACKEND` (`lm_studio` | `openai` | `vertex`)
- `EMBEDDING_MODEL` (Standard: `sentence-transformers/all-MiniLM-L6-v2`)
- Domain-Profile (`DOMAIN_ANALYSIS`, `DOMAIN_IFS`, `DOMAIN_STILISIERUNG`)
- Token-Budgets, Reranker-Parameter, Debug-Modus

---

## Tests

```bash
# Alle Tests ausführen
pytest tests/ -v

# Nur IFS-Suite
pytest tests/test_ifs_*.py -v

# Mit Coverage
pytest tests/ --cov=modules --cov-report=term-missing
```

---

## Features

### Forschung
- **Hybrid Search:** BM25 + Dense Vectors mit Reciprocal Rank Fusion
- **CitationRAG:** Rescue Mission (Essence Parity) + Zitatnachweise
- **Hermeneutische Validierung:** Confidence-Scoring, Enforcer-Prüfung, Human-in-the-Loop Sampling
- **Deterministic Pipeline:** Temperature=0.3, Seed=42, Top-P=0.85 für reproduzierbare Analysen
- **Bulk-Export:** Markdown mit YAML-Frontmatter (Reproducibility Manifest)

### Drei-Phasen-Synthese (v56)
- **Phase 1 (Draft):** Unveränderte Synthese mit vollem Kontext
- **Phase 2 (Mechanischer Check):** Deterministische Validierung — Zitat-Range, Substring-Existenz, Fuzzy-Match ≥0.85, Dokumentnamen, verwaiste Referenzen
- **Phase 3 (Korrektur):** Gezielte Selbst-Korrektur mit kurzem Prompt (~2KB), temp=0.0, flash — nur wenn Phase 2 Fehler findet
- **Titel-Mapping-Injektion:** QUELLEN-VERZEICHNIS direkt vor AUFGABE für korrekte Dokumentnamen
- **Paraphrase-Ausweg:** "Präziser Verweis OHNE Zitat ist besser als erfundenes Zitat"

### STILISTIC Mode (v57–v58)
- **Drei-Etappen-Architektur:** Etappe 1 (Python-Statistiken: Satzbau, TTR, Morphologie, Hotspot-Sätze) → Etappe 2 (LLM-Beobachtung mit Dominante + Grundoperation) → Etappe 3 (Freier Raum — kreativer Sprung)
- **Modus-Erkennung:** Automatische Erkennung des Textmodus (Polemik, Beschwörung, Nachdenken, Erzählen, Spiel) vor der Analyse — der Modus bestimmt die gesuchten Operationen
- **GRUNDOPERATION:** Zweite Analyseachse neben der Dominante — fragt nach dem operativen Eingriff des Textes (Verschiebung, Entlarvung, Verdichtung, Klangfügung etc.), nicht nach rhetorischen Figuren
- **Hypothese-erst-Logik:** Globale Synthese beginnt mit einer kühnen, aber falsifizierbaren Hypothese, dann Beweisführung mit Kategorien als Werkzeugen
- **Verdichtungsschicht:** Python extrahiert Dominante, Grundoperation, Modus und Stil-Titel pro Quelle als Konzentrat vor dem Volltext
- **Tynjanow-Integration:** Operationsvokabular statt Rhetorik-Vokabular; Methode zeigen, Form nicht vorgeben

### META-VERGLEICH (v59)
- **5-Achsen-Vergleich:** Konvergenzen, Divergenzen, Komplementarität, Grenzen, Systematischer Ertrag
- **Keine Pipeline:** Inputs sind bereits Analysen, keine Primärquellen — Einzel-LLM-Call statt mehrstufiger Pipeline
- **Zwei-Seiten-Eingabe:** Editierbare Labels, DB-Quellen oder Freitext, optionale Forschungsfrage
- **Anti-Harmonisierung:** Werkzeugvergleich, nicht Rangierung — keine synthetisierende Synthese am Ende

### Falsifizierungs-Architektur (v60)
- **Agency-Extraktion:** intentional / responsiv / entbündelnd pro Meta-Run
- **Quellen-Gegenposition (dormant):** STILISTIC-LAB-Eingang für Gegenlektüre
- **Meta-Gegenposition (Strang B):** Argumentiert GEGEN die Primäranthese
- **Meta-Adjudikation (Strang C):** Bewertet, was standhält — KEINE Harmonisierung
- **Revidierte Destillation:** Synthetisiert nur, was der Gegenprobe standhält
- **Freie Frage (Option B):** Schneller Modus (nur SEZIEREN + FREIE FRAGE) oder VOLLANALYSE-Modus
- **Meta-Meta-Ebene:** Vergleich von Meta-Läufen über Engine-Versionen hinweg

### IFS Trostbau (v54, neu in v61: Mode-Engine + Echo-Wächter + Anker-Modus)
- **Vier innere Stimmen:** IFS_FIGHT (Kampf), IFS_CONTROL (Kontrolle), IFS_FEAR (Angst), NAMASTE (Sanftheit/Würdigung)
- **Triad- und Single-Modus:** Alle drei klassischen Stimmen parallel oder einzeln, mit Wechsel-Buttons. NAMASTE als vierter, sanfterer Modus zusätzlich verfügbar.
- **Mode-abhängige Krisenschwellen (v61):** Jeder Modus hat einen eigenen Threshold für Notfall-Intervention — IFS_FIGHT=2, IFS_CONTROL=3, IFS_FEAR=2, NAMASTE=2. Eine einzelne geladene, auf Kontrolle getrimmte Stimme toleriert also mehr (Threshold 3) als eine Angst-Stimme (Threshold 2), die bei Belastung schneller eskalieren kann.
- **Echo-Wächter (v61):** Prüft nach jedem LLM-Call die Wortüberlappung zwischen User-Input und Antwort. Ab 60 % Überlappung wird einmalig neu generiert, mit dem zusätzlichen Hinweis, die Aussage vollständig umzuformulieren. Verhindert das plumpe Zurückspiegeln von User-Worten.
- **Anker-Modus (v61):** Lädt eine optionale Anker-Liste (`anker_liste.md`) als hermeneutisches Protokoll in den IFS-Prompt. Die Anker-Liste ist ein großzügiges, didaktisch aufbereitetes Lehrmaterial (privat, wird nicht mit dem Public-Repo ausgeliefert). Sie enthält konkrete Techniken für schwere Momente — z. B. die Dr.-Kappes-Technik der *Umdeutung/Beobachtung*, bei der intrusiven Gedanken wie Insekten in einem Glas betrachtet statt bekämpft werden.
- **Beziehungs-Frage proaktiv (v61):** Einmal pro Dialog wird die Frage nach der Beziehung zwischen Stimmen gestellt — nicht reaktiv, sondern aktiv vom System angestoßen.
- **LEICHTIGKEIT IST ERLAUBT (v61):** Schwere Themen brauchen auch Spielräume — die Engine darf in leichten Momenten (z. B. um eine Tasse Tee) auch einmal heiter sein.
- **Handlungsbitte-Regel (v61):** Auf „Was soll ich tun?" antwortet die Engine ehrlich mit „Das weiß ich nicht" statt zitierte Listen vorzulegen.
- **LISTE-ALS-HINTERGRUNDMATERIAL:** Anker-Listen-Items werden als Hintergrundinformation verwendet, nicht als vorgeworfene Auflistung in der Antwort.

### Importer (20+ Plattformen)
- HTML: ChatGPT, Claude, Gemini, Kimi, DeepSeek, Grok, Perplexity, LM Arena, Hotbot, GLM, Wikisource
- JSON: Gemini-Exporte, ChatGPT-Exporte, Claude-Exporte
- Dokumente: PDF, EPUB, FB2, Markdown
- Fallback: Text/Buch-Modus mit Hybrid-Chunking

---

## Documentation

- **[FIBEL](docs/FIBEL_v61.md)** – Comprehensive guide (100+ pages: concepts, architecture, tutorials)
- **[Changelog](CHANGELOG.md)** – Release notes and version history (v48 → v61)
- **[Contributing Guide](CONTRIBUTING.md)** – How to contribute (public repository)

---

## Scientific Publication

> Pantijelew, G. (2026). *Hermeneutic Reconstruction in Multi-Document RAG:
> Enforcing Source Parity through Architectural Constraints.* Zenodo.
> [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18774828.svg)](https://doi.org/10.5281/zenodo.18774828)

The paper systematically evaluates HRE against NotebookLM across four discourse archaeology
tasks (political discourse, rhetorical deconstruction, creative hypothesis validation,
prompting robustness) and provides the theoretical foundation for VIP Protection,
Essence Parity, and the Hermeneutic Enforcer.

**Case Study Video:**
[![YouTube](https://img.shields.io/badge/YouTube-HRE_Case_Study-red?logo=youtube)](https://youtu.be/HveLGOuWJM0)

---

## License & Attribution

**License:** MIT – See [LICENSE.txt](LICENSE.txt)

**Project Lead, System Design, Testing & Hermeneutic Validation:**
Grigori Pantijelew (Landesinstitut für Schule Bremen)

**Development Team:**
- **Architectural Design & Conceptual Guidance:** Claude Sonnet 4.6 (Anthropic)
- **Code Implementation & Technical Integration:** Gemini (Google DeepMind)
- **Editorial Review & Final Lektorat:** Kimi (Moonshot AI)

**Research Infrastructure:**
Google Cloud Platform (Research Credits Program, Project "Comparative Studies AI Models")

**Test Corpus (2025):**
AI dialogue datasets from DeepSeek, Kimi, ChatGPT, Claude, Gemini, Grok, GLM-4.6 (imported chat transcripts, May–December 2025)

---

### Citation (Academic Use)

**GitHub/Informal:**
```
Pantijelew, G. (2026). Hermeneutic Engine: Source Parity, Deep Validation & Chronological Synthesis.
GitHub: https://github.com/gpantijelew/hermeneutic-engine
```

**Zenodo Preprint:**
```
Pantijelew, G. (2026). Hermeneutic Reconstruction in Multi-Document RAG:
Enforcing Source Parity through Architectural Constraints.
Zenodo. https://doi.org/10.5281/zenodo.18774828
```

**BibTeX:**
```bibtex
@software{pantijelew2026hermeneutic,
  author = {Pantijelew, Grigori},
  title = {Hermeneutic Reconstruction Engine for Archaeology of Mind:
           Source Parity, Deep Validation and Chronological Synthesis in Multilingual RAG Systems},
  year = {2026},
  version = {v61},
  url = {https://github.com/gpantijelew/hermeneutic-engine},
  note = {AI-assisted development with Claude Sonnet 4.6 (Anthropic),
          Gemini (Google DeepMind), and Kimi (Moonshot AI)}
}

@article{pantijelew2026hre_paper,
  author = {Pantijelew, Grigori},
  title = {Hermeneutic Reconstruction in Multi-Document RAG:
           Enforcing Source Parity through Architectural Constraints},
  year = {2026},
  publisher = {Zenodo},
  doi = {10.5281/zenodo.18774828},
  url = {https://doi.org/10.5281/zenodo.18774828}
}
```

---

## Contributing

This repository is **public as of v55** (May 2026).

**Contributions welcome for:**
- Bug reports via GitHub Issues
- Feature requests (must align with hermeneutic methodology, see [CONTRIBUTING.md](CONTRIBUTING.md))
- Documentation improvements
- Code contributions (after discussion in Issues)

**Code contributions:** See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

**Not accepting contributions for:**
- Feature creep (AI audio/video analysis, million-document indexing)
- Breaking changes without prior discussion
- Code without tests or documentation

---

## Contact

**Project Lead:** Grigori Pantijelew
**Project Email:** hermeneutic-engine@proton.me

**Repository:** https://github.com/gpantijelew/hermeneutic-engine
**Status:** Public (v61 released August 2026)

---

## Acknowledgments

**Research Infrastructure:**
This research was supported by Google Cloud through the Google Cloud Research Credits program (Project "Comparative Studies AI Models"). Computational resources for cloud backend testing (Vertex AI) were provided by Google Cloud Platform. The primary deployment uses local infrastructure (LM Studio, ChromaDB, SQLite).

**Development Partners:**
- **Anthropic** (Claude Sonnet 4.6) – Architectural design, conceptual guidance, pre-deployment analysis
- **Google DeepMind** (Gemini) – Code implementation and technical integration
- **Moonshot AI** (Kimi) – Editorial review and final lektorat
- **GLM-5.1** – Architectural work, IFS Trostbau development (v61), and testing

**Open Source Foundations:**
- Streamlit (UI framework)
- BeautifulSoup (HTML parsing)
- rank-bm25 (keyword search)
- ChromaDB (local vector storage)
- sentence-transformers (local embeddings)