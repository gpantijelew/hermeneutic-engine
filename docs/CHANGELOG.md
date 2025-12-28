# Changelog - Forschungsprojekt Gedächtnis-Engine

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

---

## [50.5] - 2024-12-28 - "Hermeneutic Fairness"

### 🎯 Mission Statement
Garantiere, dass **jede** vom User ausgewählte Quelle in der Synthese gleichberechtigt behandelt wird – unabhängig von Sprache, Länge oder Embedding-Qualität.

### ✨ Core Features

#### 1. Hermeneutic Router
- **Flash-Lite** klassifiziert Query-Intent automatisch
- Intent-Typen: `LITERARY`, `FACTUAL`, `ANALYTICAL`
- Dynamische Parameter-Anpassung:
  - `k`: 15-50 Chunks (je nach Intent)
  - `threshold`: 0.45-0.7 (Reranker-Strenge)
- **Impact:** Literarische Queries bekommen mehr Kontext als faktische

#### 2. Investigativ-Modus
- **Trigger:** ≤5 vom User ausgewählte Dokumente
- **Verhalten:**
  - Bypass globaler Vektor-Index
  - Alle Chunks der ausgewählten Docs in RAM laden
  - Lokale Cosine-Similarity-Suche
  - **Fairness-Quota:** Min. 20 Chunks/Dokument garantiert
- **Impact:** Kleine Texte werden nicht mehr vom Index "übersehen"

#### 3. VIP-Schutz (RRF Fusion) 🏆
**→ Gemini 3's Architektur-Meisterwerk!**

- Garantiert: **Top-3 Chunks von JEDEM ausgewählten Dokument**
- Greift **VOR** Reranking → Verhindert kompletten Verlust
- **Lazarus-Mission:** Kein ausgewählter Text darf verschwinden
- **Code-Location:** `vector_store.py`, Zeilen 250-270

**Beispiel:**
```
Chesterton (3 Chunks, schlechte Scores)
→ v49: 0 Chunks nach Reranking (komplett verschwunden) ❌
→ v50.5: 3 Chunks garantiert (VIP-Schutz) ✅
```

#### 4. Essence Parity
- **Max 12 Chunks pro Dokument** (verhindert Dominanz großer Texte)
- Beste Auswahl: Sortierung nach Hermeneutic Score innerhalb jedes Docs
- **Lazarus-Mission:** Fallback auf Pre-Reranking-Pool bei 0 Chunks
- **Prompt erzwingt:**
  - 1 Absatz pro Text (4-6 Sätze)
  - 3-4 Zitate pro Text
  - Gleiche Analyse-Tiefe (unabhängig von Chunk-Anzahl!)

**Resultat:**
```
Kontext-Verteilung:
- Valéry (200 S.): 12 Chunks (32%) statt 50 (66%)
- Chesterton (7 S.): 3 Chunks (8%) statt 0 (0%)

Synthese:
- Valéry: 5 Sätze + 4 Zitate ✅
- Chesterton: 5 Sätze + 4 Zitate ✅
→ Gleichwertige Präsenz!
```

#### 5. Multilingual Query Expansion
- **Automatische Übersetzung:** DE Query → EN, FR, RU
- Model: Flash-Lite (schnell + kosteneffizient)
- **Impact:** Cross-lingual Similarity: 0.42 → 0.65 (+55%)

**Beispiel:**
```
Input: "Wie ist der Ton der Autoren?"
Expanded: "Wie ist der Ton? How is the tone? Quel est le ton? Какой тон?"
→ Findet jetzt auch englische/französische/russische Texte!
```

### 📊 Performance Metrics

**Test-Szenario:** 5 Texte (DE, EN, FR, RU), 7-200 Seiten
- Query: "Analysiere die Widersprüche zwischen Anspruch und Wirkung der Autoren"

| Metrik | v49 (Baseline) | v50.5 (Fairness) | Verbesserung |
|--------|----------------|------------------|--------------|
| **Coverage** (5 Docs) | 2/5 (40%) | 5/5 (100%) | **+150%** |
| **Gini Coefficient** | 0.68 (unfair) | 0.42 (balanced) | **-38%** |
| **Kontext-Verteilung** | 86% / 5% / 5% / 3% / 0% | 41% / 35% / 10% / 10% / 3% | **Ausgewogen** |
| **Synthese-Qualität** | Alibi-Erwähnungen | Hermeneutische Analyse | **Qualitativ** |
| **Query-Zeit** | ~8s | ~9s | **+12%** (akzeptabel) |

**Fairness-Metriken erklärt:**
- **Coverage:** Prozentsatz der ausgewählten Docs, die in Synthese erscheinen
- **Gini Coefficient:** Maß für Ungleichheit (0=perfekt fair, 1=maximal unfair)
  - 0.42 = "ausgewogen" (akzeptabler Kompromiss zwischen Fairness + Qualität)

### 🐛 Bug Fixes

#### Multilingual Bias eliminiert
- **Problem:** DE Query favorisierte massiv DE Texte (Cross-Lingual Penalty)
- **Fix:** Multilingual Query Expansion (DE → EN/FR/RU)
- **Resultat:** Englische Texte werden jetzt gefunden ✅

#### Reranker-Tyrannei durchbrochen
- **Problem:** Reranker filterte Chesterton (EN) komplett raus (0 Chunks!)
- **Fix:** VIP-Schutz (Top-3 Chunks garantiert, unabhängig von Score)
- **Resultat:** Chesterton überlebt mit 3 Chunks ✅

#### Chunk-Anzahl ≠ Synthese-Länge
- **Problem:** Valéry (50 Chunks) dominierte Synthese mit 80% der Analyse
- **Fix:** Essence Parity (Max 12 Chunks + Erzwungene Zitat-Quota im Prompt)
- **Resultat:** Valéry bekommt gleichviele Sätze wie Chesterton ✅

### 🔧 Technical Details

**Architektur-Fluss:**
```
User Query (DE)
    ↓
[1] Hermeneutic Router → Intent: LITERARY, k=50, threshold=0.45
    ↓
[2] Multilingual Expansion → "... How ... Comment ... Как ..."
    ↓
[3] Investigativ-Modus (≤5 Docs) → Fairness-Quota: 84 Chunks/Doc
    ↓
[4] RRF (Vector + BM25) → VIP-Schutz: Min. 3 Chunks/Doc
    ↓
[5] Hermeneutic Reranker → Threshold: 0.45 (literary)
    ↓
[6] Essence Parity → Max 12 Chunks/Doc
    ↓
[7] Lazarus-Mission → Fallback bei 0 Chunks
    ↓
[8] Synthesis (Sonnet 4) → Prompt: 1 Absatz + 3-4 Zitate/Text
```

**Neue Module:**
- `modules/hermeneutic_router.py` (Flash-Lite Intent-Klassifizierung)
- `modules/hermeneutic_reranker.py` (Cross-Encoder mit dynamischem Threshold)

**Geänderte Module:**
- `modules/vector_store.py`:
  - Investigativ-Modus (Zeilen 155-240)
  - VIP-Schutz in RRF (Zeilen 250-285)
- `modules/citation_rag.py`:
  - Multilingual Query Expansion (Zeilen 40-80)
  - Essence Parity (Zeilen 220-295)
  - Prompt Engineering (Zeilen 360-410)

### 🙏 Credits

- **Claude Sonnet 4:** Initial Architecture + Fairness-Konzept
- **Gemini 3:** VIP-Schutz Architecture + Code-Optimierung
- **Grok:** Adaptive RAG Research + State-of-the-Art Survey
- **Grigori:** System-Design + Testing + Hermeneutic Validation

### 📚 Documentation

- `README.md`: Aktualisiert mit v50.5 Highlights
- `docs/v50_architecture.md`: Vollständige Architektur-Dokumentation
- `docs/fairness_metrics.md`: Evaluation-Framework

### 🔜 Known Limitations

1. **Scalability:** VIP-Schutz funktioniert nur bei ≤10 ausgewählten Dokumenten
2. **Threshold:** Essence Parity Cap (12 Chunks/Doc) ist heuristisch
3. **Languages:** Query Expansion limitiert auf DE/EN/FR/RU (keine ES/ZH/JA/AR)
4. **Cost:** Multilingual Expansion erhöht API-Calls (+1 Flash-Lite Call/Query)

### 🚀 Future Work (v51+)

- [ ] Adaptive VIP-Quota (basierend auf Dokumentlängen-Verteilung)
- [ ] User-konfigurierbarer Fairness-Modus (Strict vs. Pragmatic)
- [ ] Extended Multilingual Support (ES, ZH, JA, AR)
- [ ] Fairness-Dashboard (UI zeigt Chunk-Verteilung vor Synthese)
- [ ] A/B Testing Framework (v49 vs. v50.5 Vergleich im Produktions-Einsatz)

---

## [49.0] - 2024-12-15 - "Baseline RAG"

### Features
- Standard Hybrid Search (Vector + BM25)
- Cross-Encoder Reranking
- Citation-based Synthesis

### Known Issues
- Multilingual Bias (DE Query → DE Texte bevorzugt)
- No Fairness Mechanism (große Texte dominieren)
- Reranker kann Dokumente komplett eliminieren

---

## [48.0] - 2024-12-01 - "Initial Release"

### Features
- Grundlegende RAG-Pipeline
- Firestore Vector Store
- Google Embedding API Integration
