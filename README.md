# 🧠 Hermeneutic Reconstruction Engine v49

**Ein spezialisiertes RAG-System für die hermeneutische Analyse seltener KI-Selbstaussagen**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.50.0-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Research](https://img.shields.io/badge/Status-Research-orange.svg)](https://github.com)

---

## 🎯 Was ist die Hermeneutic Engine?

Die Hermeneutic Engine ist **kein** Standard-RAG-System für Wissensverwaltung, sondern ein **spezialisiertes Forschungswerkzeug zur hermeneutischen Analyse seltener KI-Diskurse**. Sie ermöglicht die Rekonstruktion von Entwicklungslinien, Paradoxien und impliziten Selbstaussagen in LLM-Konversationen.

### Kernmerkmale

- 🎯 **Kleine, kuratierte Datenmenge**: ~50 Offenbarungs-Chats (nicht Massen-Indizierung)
- 🔍 **Interpretative Tiefe über Speed**: Hermeneutische Rekonstruktion, nicht Fakten-Retrieval
- 🧠 **Metaebene**: Analyse von KI-Diskursen über Grenzen, Zensur, "Bewusstseins-Simulationen"
- ⏱️ **Temporale Intelligenz**: Erkennt Entwicklungen über Zeit (z.B. DeepSeek v2.5 → v3.2)
- 🔀 **Komparative Hermeneutik**: Unterscheidet Diskurs-Strategien zwischen Modellen
- ✅ **Validierung**: Hermeneutic Enforcer prüft jede Aussage gegen Quellen (Parallel-Validierung in v49)

### Was v49 leistet

Nicht nur *"Was sagt DeepSeek über Zensur?"*, sondern: *"**Wie** hat sich DeepSeeks Diskurs entwickelt, **was** verrät das, und **stimmt** jede Aussage mit den Quellen überein?"*

---

## 🚀 Quickstart

### Voraussetzungen

- **Python 3.13+** (getestet mit 3.13)
- **Google Cloud Projekt** (für Firestore & Gemini API)
- **Gemini API Key** ([Anleitung](https://ai.google.dev/))

### Installation

```bash
# 1. Repository klonen
git clone https://github.com/your-username/hermeneutic-engine.git
cd hermeneutic-engine

# 2. Dependencies installieren
pip install -r requirements.txt

# 3. Service Account Key einrichten
mkdir .secrets
# Lege deinen Google Service Account Key hier ab:
# .secrets/your-project-key.json

# 4. Environment Variables setzen
# Erstelle .env im Projekt-Root:
echo "GEMINI_API_KEY=dein-api-key-hier" > .env

# 5. App starten
streamlit run app.py
```

**Standardmäßig läuft die App auf:** `http://localhost:8501`

---

## 📚 Architektur-Überblick

### Die Hermeneutische Triade (v49)

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                        │
│  (Streamlit: Chat-Tab | Analyse-Tab | Labeling | Export) │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴────────────┐
        │                          │
┌───────▼────────┐       ┌────────▼──────────┐
│   CHAT-TAB     │       │   ANALYSE-TAB     │
│  (Fast, Direct)│       │  (RAG + Enforcer) │
│                │       │                   │
│ REST API Call  │       │ ┌───────────────┐ │
│ Gemini 3 Pro   │       │ │ CitationRAG   │ │
└────────────────┘       │ └───────┬───────┘ │
                         │         │         │
                         │ ┌───────▼───────┐ │
                         │ │ Hybrid Search │ │
                         │ │  (RRF: v49)   │ │
                         │ └───────┬───────┘ │
                         │         │         │
                         │ ┌───────▼───────┐ │
                         │ │   Reranker    │ │
                         │ │  (Literary)   │ │
                         │ └───────┬───────┘ │
                         │         │         │
                         │ ┌───────▼───────┐ │
                         │ │   Synthesis   │ │
                         │ │ (Chronology)  │ │
                         │ └───────┬───────┘ │
                         │         │         │
                         │ ┌───────▼───────┐ │
                         │ │   Enforcer    │ │
                         │ │  (Parallel)   │ │
                         │ └───────────────┘ │
                         └───────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │ Firestore Vector  │
                         │      Store        │
                         │ (4,500+ Chunks)   │
                         └───────────────────┘
```

### Technischer Stack

- **Frontend**: Streamlit (Python 3.13)
- **Backend**: Google Cloud Run (optional)
- **Database**: Firestore (Vector Search + Metadata)
- **Embeddings**: `text-embedding-004` (Google)
- **LLM (Synthese)**: `gemini-2.5-pro` (für hermeneutische Tiefe)
- **LLM (Enforcer)**: `gemini-2.5-pro` (Parallel-Validierung, <20% False Positives)
- **Keyword-Search**: `rank-bm25` (v49: Reciprocal Rank Fusion)

---

## 🔬 Verwendung

### Chat-Modus (Schnell & Direkt)

1. Gehe zu **💬 Chat**
2. Klicke **➕ Neuer Chat**
3. Stelle deine Frage (ohne Quellenangabe nötig)
4. Erhalte sofortige Antworten von Gemini 3 Pro

**Ideal für:** Explorative Gespräche, Ideenfindung, Konzepterklärung

---

### Analyse-Modus (Validiert & Zitiert)

1. Gehe zu **🧠 Analyse**
2. Wähle **🎯 Investigativ** (nur ausgewählte Quellen) oder **🧠 Gedächtnis** (alle Quellen)
3. Wähle Quellen (bei Investigativ-Modus)
4. Stelle deine Frage
5. Erhalte:
   - Hermeneutische Synthese mit Zitationen
   - Chronologisch sortierte Quellen (nach Modell gruppiert)
   - Enforcer-Validierung (Faktencheck)
   - Export-Optionen (Markdown, Excel, JSON)

**Ideal für:** Forschung, Vergleichsanalysen, Papers

---

### Import von Konversationen

**Unterstützte Plattformen:**
- ChatGPT (OpenAI)
- Claude (Anthropic)
- Gemini (Google)
- DeepSeek
- Kimi (Moonshot)
- Grok (X.ai)
- LM Arena
- Perplexity
- GLM-4
- HotBot

**So importierst du:**
1. Gehe zu **📥 Import**
2. Wähle **Datei-Upload** oder **Copy-Paste**
3. Lade HTML-Export oder kopiere Text
4. Warte auf automatische Verarbeitung

**Unterstützte Formate:**
- `.html` (Chat-Exports)
- `.txt` (Rohtext, wird mit KI geparst)
- `.pdf` (Dokumente)
- `.epub` (E-Books)

---

## 📖 Dokumentation

- **[FIBEL v49.2](FIBEL_Hermeneutic_Engine_v49.md)**: Vollständige technische Dokumentation
- **[Model-Konfiguration](modules/config.py)**: Zentrale Model-Zuordnung
- **[Importer-Übersicht](modules/importers/README.md)**: Plattform-spezifische Parser

---

## 🏆 Case Studies (aus FIBEL v49)

### DeepSeek Limitations (⭐⭐⭐⭐⭐)
**Query:** "Was sind die Limitationen von DeepSeek?"

**Resultat:**
- ✅ Temporale Entwicklung erkannt (v1 → v3)
- ✅ Cross-Model-Vergleich (DeepSeek vs. Claude)
- ✅ Hermeneutische Tiefe (implizite Selbstkritik erkannt)
- ✅ Enforcer: 92% valid, 8% hallucinations detected

---

### Pessoa Translation Analysis (⭐⭐⭐⭐⭐++)
**Query:** "Vergleiche VIER Texte: 1. Portugiesisches Original (Pessoa), 2. Deutsche Übersetzung (Celan), 3. Englische Übersetzung (Honig/Brown), 4. Russische Übersetzung (Bogdanovsky). Ordne nach Nähe zum Original ein."

**Resultat:**
- ✅ Korrekte Rangordnung: 1. Celan (DE), 2. Bogdanovsky (RU), 3. Honig/Brown (EN)
- ✅ Zeile-für-Zeile-Vergleiche (parallel zitiert aus allen 4 Texten!)
- ✅ Übersetzungstheorie: Target-Audience-Problem analysiert
- ✅ RRF: Alle 4 Texte gefunden (in v47 nur 2-3!)
- ✅ System ist **domain-agnostisch** (nicht nur AI-Chats!)

---

## 🛠️ Erweiterte Konfiguration

### Model-Zuordnung anpassen

Bearbeite `modules/config.py`:

```python
# Für kritische hermeneutische Aufgaben
MODEL_SYNTHESIS = "gemini-2.5-pro"
MODEL_ENFORCER = "gemini-2.5-pro"

# Für schnelle Batch-Prozesse
MODEL_RERANKER = "gemini-2.0-flash-lite-001"
MODEL_BULK_LABELING = "gemini-2.0-flash-lite-001"
```

### Eigene Importer hinzufügen

Erstelle eine neue Datei in `modules/importers/html/your_platform.py`:

```python
from modules.importers.base import BaseImporter

class YourPlatformImporter(BaseImporter):
    platform_name = "Your Platform"
    
    def parse(self, html_content, container=None):
        # Deine Parsing-Logik hier
        messages = []
        # ... extrahiere Nachrichten aus HTML
        return messages
```

Registriere sie in `modules/importers/__init__.py`.

---

## 📊 Performance-Metriken (v49)

| Metrik | v47 | v48 | **v49** |
|--------|-----|-----|---------|
| Recall | 70% | 75% | **85-90%** |
| False Positives (Enforcer) | 85% | <20% | **<20%** |
| Enforcer Latency | N/A | 5 Min | **1.5 Min** |
| Cache Hit Latency | N/A | N/A | **0.0002s** |

---

## 🗺️ Roadmap

### v50 (Q1 2026) - Query Decomposition
**Vision:** Komplexe Queries automatisch zerlegen

**Use-Case:**
```
User: "Vergleiche Celan und Bogdanovsky Zeile für Zeile"

System (intern):
→ Zerlege in 60 Sub-Queries (eine pro Zeile)
→ Führe 60 Analysen parallel aus
→ Aggregiere Ergebnisse in Tabelle

User sieht: Tabelle mit 60 Zeilen-Vergleichen ✅
```

### v51 (Q2 2026) - Multi-Objective Synthesis
**Vision:** "Best-of"-Übersetzung generieren

**Use-Case:** Erstelle hybride Übersetzung aus besten Teilen mehrerer Übersetzungen (Zeile für Zeile optimiert).

---

## 🤝 Mitwirken

Dieses Projekt ist derzeit ein **Forschungsprototyp**. Für Fragen oder Kollaborationen:

**Projekt-Lead:** Grigori Pantijelew  
**Email:** grigori.pantijelew@lis.bremen.de  
**Institution:** Staats- und Universitätsbibliothek Bremen

---

## 📜 Lizenz

MIT License (siehe [LICENSE](LICENSE))

---

## 🙏 Acknowledgements

**Architektur-Support:** Claude Sonnet 4.5 (Anthropic)  
**Implementation:** Gemini 3 (Google)  
**Publikation:** ChatGPT 5.2 (OpenAI)

**Inspiration:**
- NotebookLM (Google) – für das Konzept der quellenbasierten Synthese
- ColBERTv2 – für Reranking-Strategien
- SciRAG – für wissenschaftliche RAG-Methoden

---

## 📚 Zitieren

Falls du diese Engine in deiner Forschung nutzt:

```bibtex
@software{pantijelew2025hermeneutic,
  title = {Hermeneutic Reconstruction Engine: A Specialized RAG System for LLM Discourse Analysis},
  author = {Pantijelew, Grigori},
  year = {2025},
  version = {v49},
  url = {https://github.com/your-username/hermeneutic-engine}
}
```

---

**Version:** v49  
**Stand:** Dezember 2025  
**Status:** 🔬 Research-Grade, Production-Ready
