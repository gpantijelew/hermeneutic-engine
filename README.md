# Hermeneutic Reconstruction Engine (HRE)

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Version](https://img.shields.io/badge/version-v59-green.svg)](CHANGELOG.md)
[![Status](https://img.shields.io/badge/status-production%20ready-brightgreen.svg)]()
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18774828.svg)](https://doi.org/10.5281/zenodo.18774828)
[![YouTube](https://img.shields.io/badge/YouTube-Case_Study-red?logo=youtube)](https://youtu.be/HveLGOuWJM0)

**Full Name:** Hermeneutic Reconstruction Engine for Archaeology of Mind
**Focus:** Source Parity, Deep Validation & Chronological Synthesis for Multilingual Text Analysis
**Stack:** Python, Streamlit, SQLite, ChromaDB, LM Studio (lokal), Vertex AI (Gemini)

Lokales Forschungswerkzeug für die Diskursarchäologie von KI-Gesprächen — mit hermeneutischer Validierung, Zitatnachweisen, Faktvalidierung, Meta-Analyse, Drei-Phasen-Synthese (Draft → Mechanischer Check → Korrektur), stilistischer Analyse (STILISTIC Mode), Meta-Vergleich analytischer Verfahren (META-VERGLEICH) und einem IFS-Resonanzraum für persönliche Reflexion.

---

## Was ist die HRE?

Die HRE ist eine **lokale, privat betriebene** Anwendung, die es ermöglicht:

- **KI-Gespräche zu importieren** (ChatGPT, Claude, Gemini, Kimi, DeepSeek, Grok, Perplexity, LM Arena, Hotbot, GLM, Wikisource, PDF, EPUB, FB2, Markdown)
- **Diskursarchäologie zu betreiben** — mit hermeneutischer Analyse, Zitatnachweisen und Faktvalidierung
- **Stilanalyse durchzuführen** — mit dem STILISTIC Mode (Drei-Etappen-Architektur: Python-Statistiken → LLM-Beobachtung → Kreativer Sprung)
- **Analytische Verfahren zu vergleichen** — mit META-VERGLEICH (5-Achsen-Vergleich: Konvergenzen, Divergenzen, Komplementarität, Grenzen, Systematischer Ertrag)
- **Forschung zu dokumentieren** — mit reproduzierbaren Analysen, Quellenangaben und einem Critical Apparatus
- **Persönliche Reflexion zu unterstützen** — über den IFS-Resonanzraum (Internal Family Systems)

Alle Daten bleiben lokal. Keine Cloud-Abhängigkeit, kein API-Key erforderlich.

---

## Schnellstart

### Voraussetzungen

- Python 3.11+
- [LM Studio](https://lmstudio.ai/) (lokaler LLM-Server) oder OpenAI API-Key
- Windows, macOS oder Linux

### Installation

```bash
# 1. Repository klonen
git clone https://github.com/gpantijelew/hermeneutic-engine.git
cd hermeneutic-engine

# 2. Virtuelle Umgebung erstellen
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. LM Studio starten (lokaler LLM-Server)
# - Modell laden (z.B. gemma-3-27b-it)
# - Server aktivieren (Standard: http://localhost:1234)

# 5. Anwendung starten
streamlit run app.py
```

Die Anwendung öffnet sich automatisch im Browser unter `http://localhost:8501`.

---

## Architektur

```
HRE/
├── app.py                    # Einstiegspunkt (Streamlit), Tab-Orchestrierung, Auth
├── modules/                  # Kernmodule
│   ├── llm_wrapper.py        # 5 LLM-Call-Varianten (LM Studio / OpenAI / Vertex), Retry-Logic
│   ├── database.py           # SQLite CRUD, FTS5, Chunk-Registry, Analyses, Enforcer-Reviews
│   ├── vector_store.py       # ChromaDB + BM25 Hybrid Search, SQLite Vector Store
│   ├── citation_rag.py       # CitationRAG mit Rescue Mission & Essence Parity
│   ├── hermeneutic_router.py # Intent-Routing (FORENSIC / EXEGESIS / SYNTHESIS / META_ANALYTICAL / STILISTIC)
│   ├── hermeneutic_reranker.py # LLM-basiertes Re-Ranking
│   ├── hermeneutic_enforcer.py # Faktvalidierung, Confidence-Scoring, Sampling
│   ├── prompt_manager.py     # YAML-zentralisierte Prompts
│   ├── text_analyzer.py      # Etappe 1: Deterministische Textstatistiken (Satzbau, TTR, Morphologie)
│   ├── stilistic_lab_pipeline.py # Etappe 2+3: STILISTIC Analyse + Globale Synthese + META-VERGLEICH
│   ├── ifs_engine.py         # IFS Resonanzraum (D.S3.7+), PromptManager + llm_call
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
│   ├── ifs_tab.py            # IFS Resonanzraum UI (Triad + Single-Modus)
│   ├── system_health_tab.py  # Health-Dashboard, Confidence Calibration, Corpus Stats
│   ├── qa_review_tab.py      # QA-Review-Queue, Enforcer-Sampling
│   ├── chat_list.py          # Sidebar: Chat-Liste mit FTS5-Suche, Lazy-Load
│   ├── settings_panel.py     # Einstellungen
│   ├── state.py              # Zentrales State-Management
│   └── components.py         # Wiederverwendbare UI-Bausteine
├── tests/                    # pytest-Suite
├── hermeneutic_protocol.yaml # Zentrale Prompt-Regeln
└── AGENTS.md                 # Projekt-Plan & Qualitätsbewertung
```

### Datenfluss

1. **Import:** HTML/JSON/PDF/EPUB → Importer → SQLite (Chats) + ChromaDB (Vektoren)
2. **Chat:** Streamlit UI → `llm_wrapper.py` → LM Studio / OpenAI / Vertex
3. **Analyse:** Query → `hermeneutic_router.py` → BM25 + Vectors → `citation_rag.py` → Synthese
4. **STILISTIC:** Text → `text_analyzer.py` (Python-Statistiken) → `stilistic_lab_pipeline.py` (LLM-Beobachtung + Synthese)
5. **META-VERGLEICH:** Zwei Analysen → `stilistic_lab_pipeline.py` → 5-Achsen-Vergleich
6. **IFS:** Situation → `ifs_engine.py` → LLM mit Situations-Injektion + Part-spezifischem Sys-Prompt

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

### IFS Resonanzraum (v54)
- **Triad-Modus:** Alle 3 inneren Stimmen parallel (Kontrolle, Kampf, Angst)
- **Single-Modus:** Eine Stimme nach der anderen, mit Wechsel-Buttons
- **Situations-Injektion:** Tagebuch-Situation fließt in jeden Sys-Prompt
- **Emergency-Interceptor:** Automatische Pause bei Selbstverletzung/Suizidalität

### Importer (20+ Plattformen)
- HTML: ChatGPT, Claude, Gemini, Kimi, DeepSeek, Grok, Perplexity, LM Arena, Hotbot, GLM, Wikisource
- JSON: Gemini-Exporte, ChatGPT-Exporte, Claude-Exporte
- Dokumente: PDF, EPUB, FB2, Markdown
- Fallback: Text/Buch-Modus mit Hybrid-Chunking

---

## Documentation

- **[FIBEL](docs/FIBEL_v50_9.md)** – Comprehensive guide (100+ pages: concepts, architecture, tutorials)
- **[Changelog](CHANGELOG.md)** – Release notes and version history (v48 → v59)
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
  version = {v59},
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
**Status:** Public (v59 released May 2026)

---

## Acknowledgments

**Research Infrastructure:**
This research was supported by Google Cloud through the Google Cloud Research Credits program (Project "Comparative Studies AI Models"). Computational resources for cloud backend testing (Vertex AI) were provided by Google Cloud Platform. The primary deployment uses local infrastructure (LM Studio, ChromaDB, SQLite).

**Development Partners:**
- **Anthropic** (Claude Sonnet 4.6) – Architectural design, conceptual guidance, pre-deployment analysis
- **Google DeepMind** (Gemini) – Code implementation and technical integration
- **Moonshot AI** (Kimi) – Editorial review and final lektorat
- **GLM-5.1** – Architectural work and testing

**Open Source Foundations:**
- Streamlit (UI framework)
- BeautifulSoup (HTML parsing)
- rank-bm25 (keyword search)
- ChromaDB (local vector storage)
- sentence-transformers (local embeddings)
