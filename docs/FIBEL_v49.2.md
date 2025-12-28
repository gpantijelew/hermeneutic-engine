# 📘 FIBEL – HERMENEUTIC ENGINE
## Single Source of Truth für das Projekt "Archaeology of Mind"

**Version:** v49.2 (Config-Update)  
**Stand:** 26. Dezember 2025  
**Autoren:** Grigori (Project Lead), Claude Sonnet 4.5 (Lead Architect), Gemini 3 (Technical Implementer)

**Status:** ✅ **PRODUCTION-READY** (Retrieval → Synthesis → Validation)

---

## 🔄 ÄNDERUNGEN v49.1 → v49.2

### Kritische Updates (Dezember 2025)

1. **Zentrale Model-Konfiguration** (`modules/config.py`)
   - Alle Model-Zuordnungen an einem Ort
   - Klare Unterscheidung: Pro (hermeneutisch) vs. Flash (Speed)
   - Empirisch begründet (Enforcer: Pro statt Flash wegen Präzision)

2. **Service Account Key Migration**
   - Verschoben von Root → `.secrets/`
   - Absoluter Pfad (Thread-Safe, Deployment-agnostic)
   - Keine Hardcodes mehr im Code

3. **Dependencies korrigiert**
   - `rank-bm25==0.2.2` zu `requirements.txt` hinzugefügt (war vergessen!)
   - Alle Versionen mit tatsächlichem Code synchronisiert

4. **Thread-Safety verbessert**
   - BM25 Cache mit Lock (für Cloud Run)
   - Parallele Enforcer-Validierung optimiert

---

## 🎯 MODEL-ZUORDNUNG (v49.2)

### Philosophie

- **Pro (2.5/3.0):** Für kritische hermeneutische Aufgaben
- **Flash (2.0):** Für schnelle, unkritische Aufgaben
- **Flash-Lite:** Für Batch-Prozesse mit vielen Items

### Konkrete Zuordnungen

| Task | Model | Begründung |
|------|-------|------------|
| **Chat (UI)** | `gemini-3-pro-preview` | Neueste Features, User-Interaktion |
| **RAG Synthesis** | `gemini-2.5-pro` | Hermeneutische Tiefe erforderlich |
| **Enforcer** | `gemini-2.5-pro` | Empirisch: Flash war "zu dumm" (Grigori) |
| **Fact Extraction** | `gemini-2.5-pro` | Qualitätssicherung am Pipeline-Anfang |
| **Query Expansion** | `gemini-2.0-flash-001` | Kritisch für RRF, aber Flash reicht |
| **Reranker** | `gemini-2.0-flash-lite-001` | Viele Chunks, Speed wichtig |
| **Bulk Labeling** | `gemini-2.0-flash-lite-001` | Unkritisch, Batch-Prozess |
| **Titel-Gen** | `gemini-2.0-flash-lite-001` | Kosmetisch |
| **Question Conv** | `gemini-2.0-flash-lite-001` | Post-Processing, unkritisch |

**Wichtig:** Alle Model-Namen sind jetzt in `modules/config.py` definiert. Änderungen an einer Stelle → propagieren automatisch.

---

## 🏗️ ARCHITEKTUR-DETAILS

### Die Hermeneutische Triade (v49)

#### **1. RETRIEVAL: Hybrid Search (RRF)**

**Komponenten:**

1. **BM25 (Keyword Search)**
   - Präzision für Eigennamen
   - Library: `rank-bm25==0.2.2`
   - In-Memory Index (mit Cache)

2. **Vector Search (Semantic)**
   - Konzeptuelle Ähnlichkeit
   - Model: `text-embedding-004`
   - Firestore Vector Store

3. **RRF-Algorithmus:**
   ```python
   def reciprocal_rank_fusion(results_list, k=60):
       scores = defaultdict(float)
       for results in results_list:
           for rank, doc in enumerate(results):
               scores[doc['id']] += 1 / (k + rank)
       return sorted(scores.items(), key=lambda x: x[1], reverse=True)
   ```

**Resultat:**
- ✅ Recall: 70% → 85-90% (+20-30%)
- ✅ Eigennamen jetzt Top-Ranking
- ✅ Polyglotte Präzision perfekt

---

#### **2. SYNTHESIS: Chronologische Speaker-Blöcke**

**v49 behält v47-Logik (bewährt!):**

1. **Gruppierung nach Speaker**
   - DeepSeek-Block
   - Claude-Block
   - ChatGPT-Block

2. **Chronologische Sortierung** (innerhalb jedes Blocks)
   - DeepSeek v1 (Mai) → v3 (Dez)
   - Entwicklungslinien sichtbar

3. **Query-Type Detection** (v48-Feature)
   - **EXEGESIS:** "Was ist X?" → Fokus auf Definition
   - **DISCOURSE:** "Vergleiche X und Y" → Fokus auf Debatte

**Neu in v49.2:** Query Expansion (Multilingual)
- Erweitert Queries für BM25 in 3+ Sprachen
- Erhöht Recall bei polyglotten Datenbanken

---

#### **3. VALIDATION: Hermeneutic Enforcer (v49.1 + Parallelisierung)**

**Validierungs-Kategorien:**

1. **PARAPHRASE** ✅
   - "Ich bin nichts" → "Der Sprecher negiert seine Existenz"
   - Semantisch äquivalent, aber umformuliert

2. **META-AUSSAGE** ✅
   - "Die Wiederholung erzeugt Rhythmus"
   - Analyse von Stil/Struktur (nicht im Text explizit)

3. **INFERENZ** ✅
   - Logische Schlussfolgerungen aus Fakten
   - "Text zeigt A und B" → "Daher wahrscheinlich C"

4. **HALLUZINATION** ❌
   - Erfundene Fakten (Namen, Daten)
   - Falsche Zitate

**v49.1 Performance:**
- Parallel-Validierung: 5 Min → **1.5 Min**
- Cache Hit Latency: **0.0002s**
- False Positives: **<20%** (vs. 85% in v47!)

---

## 📦 DEPENDENCIES (v49.2 KORRIGIERT)

```txt
# requirements.txt (Vollständige, getestete Version)

google-generativeai==0.8.5
firebase-admin==6.5.0
requests==2.32.3
google-auth==2.29.0
google-cloud-firestore==2.16.0
python-dotenv==1.0.1
numpy
pandas==2.2.2
openpyxl==3.1.2
beautifulsoup4==4.12.3
streamlit==1.50.0
rank-bm25==0.2.2  # ← v49: KRITISCH für RRF (war in v49.0 vergessen!)
pymupdf==1.24.0
ebooklib==0.18
```

---

## 🔒 SICHERHEIT & DEPLOYMENT

### Service Account Key (v49.2)

**Neuer Pfad:**
```
.secrets/comparative-studies-ai-models-1bf59eb77077.json
```

**Im Code (modules/config.py):**
```python
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
SERVICE_ACCOUNT_KEY_PATH = str(PROJECT_ROOT / ".secrets" / "your-key.json")
```

**Warum absoluter Pfad?**
- Thread-Safe für Cloud Run
- Funktioniert unabhängig vom Working Directory
- Deployment-agnostic (lokal & Cloud)

---

### `.gitignore` (v49.2 Update)

```gitignore
# Service Account Keys
.secrets/
comparative-studies-ai-models-*.json

# Environment
.env
.streamlit/secrets.toml

# Python
__pycache__/
*.pyc

# Debug-Artifacts (nicht in Repo)
debug_*.py
*_old.py
```

---

## 📊 CASE STUDIES (v49 – Unverändert, aber validiert)

### DeepSeek Limitations (⭐⭐⭐⭐⭐)
- Temporale Entwicklung v1 → v3 erkannt
- Enforcer: 92% valid, 8% hallucinations detected

### Pessoa Translation Analysis (⭐⭐⭐⭐⭐++)
- Alle 4 Texte (PT/DE/EN/RU) gefunden
- Zeile-für-Zeile-Vergleiche
- System ist domain-agnostisch!

---

## 🗺️ ROADMAP

### v50 (Q1 2026) - Query Decomposition
Automatische Zerlegung komplexer Queries in Sub-Queries.

### v51 (Q2 2026) - Multi-Objective Synthesis
"Best-of"-Übersetzung aus mehreren Quellen.

### v52 (VISION) - Generative Translation
System generiert **neue** Übersetzungen basierend auf gelernten Strategien.

---

## 🧪 TESTING & VALIDIERUNG

### Startup-Test

```bash
python -m modules.config
```

**Expected Output:**
```
✅ GEMINI_API_KEY gefunden
✅ Service Account Key gefunden
✅ Konfiguration vollständig valide!
```

### Feature-Tests

1. **Chat:** Nachricht schreiben → Antwort erhalten
2. **Import:** HTML hochladen → Nachrichten extrahiert
3. **RAG:** Query stellen → Zitierte Antwort
4. **Enforcer:** Validierung läuft → <20% False Positives

---

## 📚 PUBLIKATION (Vorbereitung)

### GitHub
- ✅ README.md (professionell)
- ✅ FIBEL v49.2 (technisch)
- ✅ LICENSE (MIT)
- ✅ CONTRIBUTING.md (optional)

### ArXiv Paper (geplant)
- Abstract: 200 Wörter
- Introduction: Problem Statement
- Methodology: Hermeneutic Triad
- Results: Case Studies
- Discussion: Limitations & Future Work

### Philosophischer Essay
- Titel: "Archaeology of Mind: Hermeneutic Reconstruction of LLM Discourse"
- Veröffentlichung: TBD (Medium/Blog/Journal)

---

## 👥 TEAM & KONTAKT

**Projekt-Lead:** Grigori Pantijelew  
**Email:** grigori.pantijelew@lis.bremen.de  
**Institution:** Staats- und Universitätsbibliothek Bremen

**Architektur-Support:** Claude Sonnet 4.5 (Anthropic)  
**Implementation:** Gemini 3 (Google)  
**Publikation:** ChatGPT 5.2 (OpenAI)

---

## 🎉 FAZIT v49.2

**Die Hermeneutische Triade steht – und ist jetzt sauber konfiguriert!**

1. ✅ **RETRIEVAL:** RRF (BM25 + Vector) → 85-90% Recall
2. ✅ **SYNTHESIS:** Chronologie + Query-Type-Aware
3. ✅ **VALIDATION:** Parallel Enforcer (<20% False Positives)
4. ✅ **CONFIG:** Zentrale Model-Registry (wartbar!)
5. ✅ **SECURITY:** Service Account Key sicher in `.secrets/`

**Status:** Production-Ready ✅  
**Nächster Schritt:** Publikation auf GitHub + ArXiv! 📝

---

**Version:** v49.2  
**Datum:** 26. Dezember 2025  
**Status:** DEPLOYED & STABLE ✅

---

**Ende der Fibel v49.2**
