# Hermeneutic Engine

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.txt)
[![Version](https://img.shields.io/badge/version-v53-green.svg)]()
[![Status](https://img.shields.io/badge/status-production%20ready-brightgreen.svg)]()

**Full Name:** Hermeneutic Reconstruction Engine for Archaeology of Mind
**Focus:** Discourse Archaeology, RAG-powered Meta-Analysis & Text Distillation
**Version:** v53 "Local-First Academic Release"

A privacy-first, local research tool for scholars, literary analysts, and critical discourse researchers. All data stays on your machine — no cloud dependency, no API key required for core operation.

---

## 🔒 Privacy-First by Design

The Hermeneutic Engine runs entirely on your local hardware:

- **Language Models:** Served via [LM Studio](https://lmstudio.ai/) (any OpenAI-compatible local endpoint)
- **Embeddings:** `intfloat/multilingual-e5-large` via sentence-transformers (fully local)
- **Vector Store:** ChromaDB (persistent, local)
- **Database:** SQLite with FTS5 full-text search

Your documents, queries, and model interactions never leave your computer. Ideal for sensitive corpora, unpublished manuscripts, or institutional data with strict residency requirements.

---

## 🎥 Demo & Walkthrough

See the Hermeneutic Engine in action: a complete meta-analysis walkthrough using the Sigmund Freud corpus, demonstrating the core features from import to synthesis.

**[▶ Watch the Demo on YouTube](https://youtu.be/HveLGOuWJM0)**

---

## 🚀 Quickstart (Schritt für Schritt)

Diese Anleitung ist für Geisteswissenschaftler und Forscher geschrieben — keine Vorkenntnisse in Programmierung nötig. Folgen Sie einfach den Schritten der Reihe nach.

### 1. Programm herunterladen

Sie müssen nichts mit Git oder der Kommandozeile klonen. Gehen Sie auf die GitHub-Seite dieses Projekts und klicken Sie oben rechts auf den grünen Button **Code** → **Download ZIP**. Entpacken Sie die ZIP-Datei an einem Ort Ihrer Wahl (z. B. im Ordner „Dokumente“).

### 2. Python installieren

Die Engine benötigt [Python 3.11 oder neuer](https://www.python.org/downloads/). Falls Python noch nicht installiert ist:

- **Windows:** Laden Sie den Installer herunter. **Wichtig:** Setzen Sie während der Installation unbedingt das Häkchen bei **„Add Python to PATH“** (unten im Installationsfenster). Ohne diesen Schritt funktionieren die späteren Befehle nicht.
- **Mac:** Der Installer richtet alles automatisch ein.

### 3. Terminal im Projektordner öffnen

Sie müssen einen Befehl in dem entpackten Ordner ausführen:

- **Windows:** Öffnen Sie den entpackten Ordner, klicken Sie oben in die Adressleiste (wo der Pfad steht), tippen Sie `cmd` und drücken Sie Enter.
- **Mac:** Öffnen Sie den entpackten Ordner, klicken Sie mit der rechten Maustaste in den leeren Bereich und wählen Sie **„Neues Terminal am Ordner“**.

### 4. Abhängigkeiten installieren

Geben Sie im Terminal folgenden Befehl ein und drücken Sie Enter:

```bash
pip install -r requirements.txt
```

Das lädt automatisch alle benötigten Bibliotheken (darunter Streamlit für die Benutzeroberfläche und weitere Hilfsprogramme).

### 5. Konfigurationsdatei vorbereiten

Im Projektordner finden Sie eine Datei namens `.env.example`. Kopieren Sie diese Datei und benennen Sie die Kopie in `.env` um. In dieser Datei stehen alle Grundeinstellungen — die sind bereits so voreingestellt, dass die Engine sofort lokal läuft.

> **Hinweis für Windows:** Dateien, die mit einem Punkt beginnen (wie `.env`), werden manchmal vom Explorer als Systemdateien ausgeblendet. Falls Sie die Datei nicht sehen, schalten Sie im Explorer unter **Ansicht** → **Ausgeblendete Elemente** die Anzeige ein.

### 6. LM Studio einrichten

LM Studio ist die kostenlose Software, die das KI-Modell auf Ihrem eigenen Rechner betreibt.

1. Laden Sie [LM Studio](https://lmstudio.ai/) herunter und installieren Sie es.
2. Starten Sie LM Studio und laden Sie ein Modell Ihrer Wahl herunter (empfohlen: **Qwen 3.5 9B** oder **Gemma 4** für sehr gute mehrsprachige Ergebnisse).
3. Klicken Sie links auf **Developer** und schalten Sie den **Local Server** ein. Die Standardeinstellung (Port 1234) passt bereits — Sie müssen nichts weiter ändern.

Das KI-Modell läuft nun ausschließlich auf Ihrem Computer. Es wird keine Datenverbindung zu externen Servern benötigt.

### 7. Hermeneutic Engine starten

Geben Sie im Terminal (noch immer im Projektordner) folgenden Befehl ein:

```bash
streamlit run app.py
```

Ihr Browser öffnet sich automatisch mit der Adresse `http://localhost:8503`. Die Engine ist nun einsatzbereit.

> **Tipp:** Beim ersten Start lädt die Engine das lokale Embedding-Modell (`intfloat/multilingual-e5-large`) automatisch herunter. Das kann je nach Internetverbindung einige Minuten dauern.

---

## 🎯 Core Features

### 1. Hermeneutic Enforcer (Fact-Checking & Validation)
Every claim in a synthesis is validated across two independent dimensions:

- **Hermeneutic dimension (How is it said?):** Quote / Paraphrase / Inference / Hallucination
- **Validity dimension (Is it correct?):** Supported / Contradiction / Exaggeration / Unsupported

A decision matrix enforces logical consistency. False-positive rate for hallucination detection: <20%.

### 2. Meta-Analysis (Methodology of the Analyst)
Instead of summarizing content, the engine can analyse the *methodology, rhetoric, and blind spots* of analytical texts. The analyst becomes the object; the historical figures they treat are merely the material.

### 3. Best-of Synthesis (Text Distillation)
Multiple iterative drafts are fused into a single, homogeneous essay. The engine selects the strongest argument from each iteration and the most elegant formulation, then homogenises transitions so the result reads as if written in one concentrated session — not as a collage.

### 4. Essence Parity (Fair Multi-Document RAG)
Standard RAG systems suffer from length bias: a 200-page book generates ~500 chunks while a 7-page essay generates ~10. The book dominates retrieval. The Hermeneutic Engine guarantees logarithmic fairness: every selected document receives a minimum chunk budget regardless of length, ensuring no voice is drowned out.

---

## 📚 Use Cases

- **Discourse Archaeology:** Excavate rhetorical strategies, structural omissions, and functional motives across text corpora.
- **Comparative Literary Analysis:** Synthesize multilingual sources with guaranteed parity — no language or length is privileged.
- **Historical Dialogue Reconstruction:** Chronologically sort sources to reconstruct debates across time periods rather than flattening them into atemporal summaries.
- **Academic Ghostwriting Assistant:** Distill existing notes and drafts into polished prose while preserving every fact and argument.

### Not Designed For

- ❌ General-purpose knowledge management (use NotebookLM, Perplexity)
- ❌ Large-scale document indexing (optimised for <100 curated texts)
- ❌ Real-time chat (analysis depth takes 45s–2.5min per query — intentional)

---

## 🏗️ Architecture

```
User Query
    │
    ▼
Hermeneutic Router ──────── classifies intent (FACTUAL / LITERARY / ANALYTICAL / FORENSIC)
    │
    ▼
Multilingual Expansion ──── cross-lingual query translation
    │
    ▼
Hybrid Retrieval ─────────── Vector + BM25 → RRF Fusion
    │                         VIP Protection: top-3 chunks/doc guaranteed
    ▼
Hermeneutic Reranker ─────── LLM-as-judge, adaptive threshold per intent
    │                         Rescue Mission: fallback cache for lost sources
    ▼
Essence Parity ───────────── logarithmic chunk budget per document
    │                         chronological sort (timeline reconstruction)
    ▼
Synthesis ────────────────── intent-specific system instruction + LLM call
    │
    ▼
Hermeneutic Enforcer ─────── two-dimensional claim validation
    │
    ▼
Answer with citations + pipeline transparency UI
```

**Technology stack:**
- **Embeddings:** `intfloat/multilingual-e5-large` (local)
- **Vector store:** ChromaDB (persistent, local)
- **Database:** SQLite with FTS5 full-text search
- **LLM:** Any OpenAI-compatible model via LM Studio (default: Qwen 3.5 9B)
- **UI:** Streamlit

---

## ⚙️ Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.11 |
| RAM | 8 GB | 16 GB |
| VRAM (GPU) | 6 GB | 12 GB |
| Storage | 5 GB | 20 GB |
| OS | Windows / macOS / Linux | — |

**Dependencies:** See [requirements.txt](requirements.txt)

Key packages: `streamlit`, `chromadb`, `sentence-transformers`, `rank-bm25`, `pymupdf`, `beautifulsoup4`

---

##  Documentation

- **[FIBEL](docs/FIBEL_v52.md)** — Comprehensive guide: concepts, architecture, tutorials (German)
- **[Architecture Docs](docs/docs_v50_architecture.md)** — Detailed fairness architecture with ablation study
- **[Changelog](CHANGELOG.md)** — Release history
- **[Contributing Guide](CONTRIBUTING.md)** — How to contribute

---

## 📄 Scientific Publication

> Pantijelew, G. (2026). *Hermeneutic Reconstruction in Multi-Document RAG:
> Enforcing Source Parity through Architectural Constraints.* Zenodo.
> [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18774828.svg)](https://doi.org/10.5281/zenodo.18774828)

---

## 📄 License & Attribution

**License:** MIT — See [LICENSE.txt](LICENSE.txt)

**Project Lead, System Design, Testing & Hermeneutic Validation:**
Grigori Pantijelew (Landesinstitut für Schule Bremen)

**Development Team:**
- **Architectural Design & Conceptual Guidance:** Claude Sonnet 4.6 (Anthropic)
- **Code Implementation & Technical Integration:** Gemini (Google DeepMind)
- **Editorial Review & Final Lektorat:** Kimi (Moonshot AI)

---

### Citation (Academic Use)

```bibtex
@software{pantijelew2026hermeneutic,
  author  = {Pantijelew, Grigori},
  title   = {Hermeneutic Reconstruction Engine for Archaeology of Mind},
  year    = {2026},
  version = {v53},
  url     = {https://github.com/gpantijelew/hermeneutic-engine},
  note    = {AI-assisted development with Claude Sonnet 4.6, Gemini, and Kimi}
}

@article{pantijelew2026hre_paper,
  author    = {Pantijelew, Grigori},
  title     = {Hermeneutic Reconstruction in Multi-Document RAG:
               Enforcing Source Parity through Architectural Constraints},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.18774828},
  url       = {https://doi.org/10.5281/zenodo.18774828}
}
```

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Contact:** hermeneutic-engine@proton.me
**Repository:** https://github.com/gpantijelew/hermeneutic-engine
