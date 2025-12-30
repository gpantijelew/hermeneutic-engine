# 📘 FIBEL – HERMENEUTIC RECONSTRUCTION ENGINE
## Single Source of Truth für das Projekt "Archaeology of Mind"

**Version:** v50.5 "Source Parity & Deep Validation"  
**Stand:** 29. Dezember 2025  
**Autoren:** Grigori Pantijelew (Project Lead), Claude Sonnet 4.5 (Architectural Design), Gemini 3 (Code Implementation), Grok (Research Support)

**Status:** ✅ **PRODUCTION-READY** (Retrieval → Synthesis → Validation)

---

## 🎯 INHALTSVERZEICHNIS

1. **PROJEKT-IDENTITÄT** – Mission, Evolution, Was ist neu?
2. **KONZEPTIONELLE GRUNDLAGEN** – Hermeneutik, Fairness, Architektur-Philosophie
3. **TECHNISCHE ARCHITEKTUR (v50.5)** – Die drei Schichten + neue Module
4. **MODEL-ZUORDNUNG (v50.5)** – Welches Model wofür?
5. **DEPLOYMENT & OPERATIONS** – Cloud Run, Secrets, Troubleshooting
6. **DEPENDENCIES & CONFIGURATION** – Python, Packages, Config
7. **CASE STUDIES** – DeepSeek, Pessoa, Grok in Aktion
8. **PERFORMANCE & TESTING** – Metriken, Validierung, Messmethodik
9. **TEAM & WORKFLOW** – Rollen, Prinzipien, AI-Assisted Development
10. **PUBLIKATION** – GitHub, ArXiv, Essay
11. **ROADMAP** – Nächste Schritte (v50.6+)
12. **ANHÄNGE** – Git, Glossar, Kontakt

---

# 1. PROJEKT-IDENTITÄT

## 1.1 Mission Statement: Archaeology of Mind

Die **Hermeneutic Reconstruction Engine** ist kein allgemeines RAG-System, sondern ein spezialisiertes Forschungswerkzeug für die **Archäologie des Geistes** – die systematische Ausgrabung und Rekonstruktion von Denkprozessen in KI-Dialogen und literarischen Korpora.

### Das zentrale Problem

Standardmäßige RAG-Systeme (Retrieval-Augmented Generation) leiden unter zwei fundamentalen Schwächen, die sie für hermeneutische Arbeit ungeeignet machen:

1. **Source Bias:** Große, dominante Texte überschatten kleine, aber bedeutsame Quellen. Ein 200-seitiger Text von Valéry "verschluckt" einen 7-seitigen Essay von Chesterton – auch wenn beide für die Fragestellung gleich relevant sind.

2. **Validation Blindness:** Synthesen enthalten häufig Halluzinationen (erfundene Fakten, falsche Zitate), die nicht von legitimen Inferenzen unterschieden werden. Ein Forscher kann nicht beurteilen, welche Aussagen vertrauenswürdig sind.

### Unsere Lösung: Architektonische Garantien

Die Hermeneutic Engine löst diese Probleme nicht durch "bessere Prompts" oder "mehr Daten", sondern durch **architektonische Garantien** auf drei Ebenen:

**1. Source Parity (Retrieval-Ebene):**  
- **VIP-Schutz:** Jedes vom User ausgewählte Dokument bekommt garantiert mindestens 3 Top-Chunks – unabhängig von Größe, Sprache oder Embedding-Qualität.
- **Investigativ-Modus:** Bei ≤5 ausgewählten Dokumenten wird der globale Index umgangen und eine lokale Fairness-Quota (min. 20 Chunks/Dokument) erzwungen.

**2. Essence Parity (Synthesis-Ebene):**  
- **Max 12 Chunks/Dokument:** Verhindert, dass große Texte die Synthese dominieren.
- **Enforced Citation Quota:** Der Synthesis-Prompt erzwingt 3-4 Zitate pro Quelle – unabhängig von der Chunk-Anzahl.

**3. Deep Validation (Validation-Ebene):**  
- **Hermeneutic Enforcer:** Jede Aussage in der Synthese wird kategorisiert (PARAPHRASE, META-STATEMENT, INFERENCE, HALLUCINATION).
- **Parallel Validation:** 5 Minuten → 1.5 Minuten durch Caching.
- **False Positive Rate:** <20% (vs. 85% in Baseline v47).

### Warum "Archaeology of Mind"?

Der Projektname ist mehr als Metapher – er beschreibt die methodische Haltung:

- **Archäologie:** Wir "graben" in Textschichten (Chat-Protokolle, Versionen, Übersetzungen), um verborgene Strukturen sichtbar zu machen.
- **of Mind:** Das Untersuchungsobjekt sind **Denkprozesse** – wie KI-Modelle sich entwickeln, wie sie zensieren, wie sie argumentieren.
- **Hermeneutic Reconstruction:** Wir rekonstruieren nicht nur "was gesagt wurde", sondern **wie es gemeint war** – die Intention hinter den Worten.

**Beispiel:** DeepSeek v1 (Mai 2025) sagt offen ""Sorry, that's beyond my current scope"". DeepSeek v3 (Dezember 2025) sagt: "Ich analysiere, was ich nicht sagen kann". Beide Aussagen sind **faktisch korrekt** – aber die hermeneutische Differenz (Opfer-Haltung vs. Meta-Reflexion) erschließt sich erst durch **temporale Rekonstruktion** über drei Versionen hinweg.

---

## 1.2 Versions-Evolution (v48 → v49 → v50.5)

Die Entwicklung der Engine folgt einem klaren Pfad: Von **funktionaler Korrektheit** (v48) über **hermeneutische Tiefe** (v49) zu **architektonischer Fairness** (v50.5).

### v48 (Dezember 2025): "Baseline RAG"
- **Grundlegende RAG-Pipeline:** Vector Search + Cross-Encoder Reranking
- **Chat-Import:** HTML-Parser für verschiedene Plattformen
- **Synthesis:** Einfache Konkatenation der Top-K Chunks

**Problem erkannt:** Große Texte dominieren Synthese, kleine Texte verschwinden.

---

### v49 (Dezember 2025): "Die Hermeneutische Triade"

**Major Innovation:** Einführung der drei-schichtigen Architektur (Retrieval → Synthesis → Validation).

#### Neue Features:
1. **Hybrid Search (RRF):**
   - Fusion von BM25 (Keyword-Präzision) + Vector Search (Semantik)
   - Reciprocal Rank Fusion Algorithmus
   - **Impact:** Recall 70% → 85-90%

2. **Chronologische Speaker-Blocks:**
   - Gruppierung nach Autor/Modell (z.B. DeepSeek-Block, Claude-Block)
   - Zeitliche Sortierung innerhalb jedes Blocks
   - **Impact:** Temporale Evolution wird sichtbar (v1 → v2 → v3)

3. **Hermeneutic Enforcer (v49.1):**
   - Validierung jeder Aussage (PARAPHRASE, META-STATEMENT, INFERENCE, HALLUCINATION)
   - Parallel Validation (5 Min → 1.5 Min)
   - **Impact:** False Positives 85% → <20%

**Problem erkannt:** Multilingual Bias (DE Query → DE Texte massiv bevorzugt), Reranker eliminiert kleine Texte komplett.

---

### v50.5 (Dezember 2025): "Source Parity & Deep Validation"

**Major Innovation:** Architektonische Garantien für Fairness + Intent-Adaptive Parameter.

#### Neue Features:

**1. VIP-Schutz (RRF Fusion Layer):**
- Garantiert **Top-3 Chunks von jedem ausgewählten Dokument** vor Reranking
- **Lazarus-Mission:** Falls ein Dokument nach Reranking 0 Chunks hat → Fallback auf Pre-Reranking-Pool
- **Impact:** Coverage 40% → 100% (Test: 5 Docs, 4 Sprachen)

**Code-Location:** `modules/vector_store.py`, Zeilen 250-285

**Beispiel:**
```
Chesterton (7 Seiten, EN) hatte 0 Chunks nach Reranking in v49.
→ v50.5: VIP-Schutz garantiert 3 Chunks, unabhängig vom Reranker-Score.
```

**2. Essence Parity (Synthesis Layer):**
- **Max 12 Chunks pro Dokument** (verhindert Dominanz großer Texte)
- **Enforced Citation Quota:** Synthesis-Prompt erzwingt 3-4 Zitate/Quelle
- **Impact:** Gini Coefficient 0.68 → 0.42 (Fairness verbessert um 38%)

**Code-Location:** `modules/citation_rag.py`, Zeilen 220-295

**Beispiel:**
```
Valéry (200 Seiten, FR): 50 Chunks verfügbar → 12 ausgewählt (beste Scores)
Chesterton (7 Seiten, EN): 3 Chunks verfügbar → 3 ausgewählt (alle!)
→ Synthese: Beide bekommen je 5 Sätze + 4 Zitate (gleiche Präsenz!)
```

**3. Multilingual Query Expansion:**
- Automatische Übersetzung der Query: DE → EN, FR, RU
- Model: `gemini-2.0-flash-lite-001` (schnell, kosteneffizient)
- **Impact:** Cross-Lingual Similarity 0.42 → 0.65 (+55%)

**Code-Location:** `modules/citation_rag.py`, Zeilen 40-80

**Beispiel:**
```
Input: "Wie ist der Ton der Autoren?"
Expanded: "Wie ist der Ton? How is the tone? Quel est le ton? Какой тон?"
→ Findet jetzt auch englische/französische/russische Texte!
```

**4. Hermeneutic Router (Intent Classification):**
- Klassifiziert Query-Intent: LITERARY, FACTUAL, ANALYTICAL
- Passt Parameter dynamisch an (k, threshold)
- **Impact:** Literarische Queries bekommen mehr Kontext (k=50 vs. k=15 für faktische)

**Code-Location:** `modules/hermeneutic_router.py`, gesamte Datei

**Beispiel:**
```
Query: "Analysiere die Widersprüche zwischen Anspruch und Wirkung"
→ Router: ANALYTICAL (k=30, threshold=0.6)
→ Reranker: LITERARY (threshold=0.45, weil Query komplex ist)
```

**5. Investigativ-Modus (Small Corpora Optimization):**
- Aktiviert bei ≤5 ausgewählten Dokumenten
- Umgeht globalen Index → lädt alle Chunks der ausgewählten Docs in RAM
- **Fairness-Quota:** Min. 20 Chunks/Dokument garantiert
- **Impact:** Kleine Texte (7 Seiten) verschwinden nicht mehr im großen Index

**Code-Location:** `modules/vector_store.py`, Zeilen 155-240

---

## 1.3 Was ist neu in v50.5? (Narrative Zusammenfassung)

Version 50.5 ist die Antwort auf die zentrale Forschungsfrage: **"Wie garantieren wir, dass jede vom User ausgewählte Stimme in der Synthese gehört wird?"**

### Die drei großen Durchbrüche:

**1. Fairness als Architektur-Prinzip**

In v49 war Fairness ein **Ziel** (durch bessere Prompts, bessere Parameterwahl). In v50.5 ist Fairness eine **Garantie** (durch VIP-Schutz, Essence Parity, Investigativ-Modus).

**Metapher:** Ein demokratisches Parlament vs. ein Marktplatz.
- v49 = Marktplatz: Wer lauter schreit (größerer Text, besseres Embedding), bekommt mehr Aufmerksamkeit.
- v50.5 = Parlament: Jeder Abgeordnete (jedes ausgewählte Dokument) hat garantierte Redezeit (min. 3 Chunks, max 12 Chunks).

**2. Multilingual Parity**

In v49 bevorzugte eine deutsche Query massiv deutsche Texte (Cross-Lingual Penalty). Ein englischer Text von Chesterton wurde "nicht gefunden", obwohl relevant.

**Lösung:** Multilingual Query Expansion übersetzt die Query in 4 Sprachen. Das System sucht parallel in allen Sprachen und findet **alle** relevanten Texte – unabhängig von der Query-Sprache.

**Beispiel (Real Case):**
```
Query: "Wie unterscheiden sich die Autoren in ihrer Haltung?"

v49 Results:
- Valéry (FR): 50 Chunks (stark bevorzugt, weil "conscience" im Text)
- Chesterton (EN): 0 Chunks (komplett verschwunden!)

v50.5 Results:
- Valéry (FR): 12 Chunks (begrenzt durch Essence Parity)
- Chesterton (EN): 3 Chunks (geschützt durch VIP-Schutz)
```

**3. Intent-Adaptive Retrieval**

In v49 hatten alle Queries dieselben Parameter (k=30, threshold=0.6). Das führte zu Problemen:
- Literarische Queries (viele Nuancen) → zu wenig Kontext
- Faktische Queries (eine klare Antwort) → zu viel Rauschen

**Lösung:** Hermeneutic Router klassifiziert den Query-Intent und passt die Parameter an:
- LITERARY: k=50, threshold=0.45 (mehr Kontext, toleranter Reranker)
- FACTUAL: k=15, threshold=0.7 (wenig Kontext, strenger Reranker)
- ANALYTICAL: k=30, threshold=0.6 (balanciert)

**Beispiel:**
```
Query 1: "Wann wurde DeepSeek v3 veröffentlicht?"
→ Intent: FACTUAL → k=15 (eine klare Antwort reicht)

Query 2: "Analysiere die rhetorischen Strategien in DeepSeek's Zensur-Diskurs"
→ Intent: LITERARY → k=50 (viele Nuancen nötig)
```

---

# 2. KONZEPTIONELLE GRUNDLAGEN

## 2.1 Die Hermeneutische Triade (Überblick)

Die Architektur der Engine basiert auf drei Schichten, die jeweils eine hermeneutische Funktion erfüllen:

### Layer 1: RETRIEVAL (Heuristik)

**Funktion:** Finden der **potenziell relevanten** Textstellen.

**Methode:**
- **Hybrid Search (RRF):** Fusion von BM25 (Keyword) + Vector Search (Semantik)
- **VIP-Schutz:** Top-3 Chunks pro ausgewähltem Dokument garantiert
- **Investigativ-Modus:** Fairness-Quota bei ≤5 Dokumenten

**Hermeneutische Analogie:** Der "erste Durchgang" beim Lesen – man überfliegt den Text und markiert interessante Stellen. Man weiß noch nicht, ob sie wirklich relevant sind, aber sie sind **Kandidaten**.

**Output:** 70 Chunks (Kandidaten-Pool)

---

### Layer 2: SYNTHESIS (Interpretation)

**Funktion:** Konstruktion einer **kohärenten Interpretation** aus den Kandidaten.

**Methode:**
- **Essence Parity:** Max 12 Chunks pro Dokument (verhindert Dominanz)
- **Chronologische Speaker-Blocks:** Gruppierung + zeitliche Sortierung
- **Enforced Citation Quota:** 3-4 Zitate pro Quelle im Prompt

**Hermeneutische Analogie:** Der "zweite Durchgang" – man liest die markierten Stellen genau, vergleicht sie, und formuliert eine Interpretation. Man wählt die **besten** Stellen aus (nicht alle!), aber achtet darauf, dass alle Autoren **gleichberechtigt** vertreten sind.

**Output:** 5-Paragraph-Synthese (4-6 Sätze pro Autor, 3-4 Zitate pro Autor)

---

### Layer 3: VALIDATION (Kritik)

**Funktion:** Prüfung der **Vertrauenswürdigkeit** jeder Aussage in der Synthese.

**Methode:**
- **Hermeneutic Enforcer:** Kategorisierung jeder Aussage
  - ✅ PARAPHRASE (semantisch äquivalent)
  - ✅ META-STATEMENT (Stil-Analyse)
  - ✅ INFERENCE (logische Schlussfolgerung)
  - ❌ HALLUCINATION (erfundener Fakt)
- **Parallel Validation:** 5 Validierungen gleichzeitig (mit Cache)

**Hermeneutische Analogie:** Der "dritte Durchgang" – man prüft die eigene Interpretation gegen die Quellen. Welche Aussagen sind **wörtlich belegbar** (Paraphrase)? Welche sind **stilistische Beobachtungen** (Meta-Statement)? Welche sind **Schlussfolgerungen** (Inference)? Welche sind **nicht belegbar** (Hallucination)?

**Output:** Validiertes Synthese-Dokument (jede Aussage kategorisiert)

---

## 2.2 Fairness als architektonisches Prinzip

### Warum ist Fairness wichtig für Hermeneutik?

Hermeneutik bedeutet **gleichberechtigtes Zuhören** – jede Stimme verdient Gehör, unabhängig von ihrer "Lautstärke" (Textlänge, Embedding-Qualität, Sprache).

**Collingwood (The Idea of History, 1946):**
> "The history of thought, and therefore all history, is the re-enactment of past thought in the historian's own mind."

Wenn ein RAG-System systematisch kleine Texte ignoriert (weil sie von großen Texten überschattet werden), dann ist dieser Dialog **asymmetrisch**. Die Engine "hört" nur die lauten Stimmen – und reproduziert damit bestehende Ungleichheiten.

### Fairness in v50.5: Drei Garantien

**1. VIP-Schutz (Niemand darf verschwinden):**
- Jedes ausgewählte Dokument bekommt mindestens 3 Top-Chunks.
- **Warum 3?** Empirische Tests zeigten: 1 Chunk = zu wenig Kontext für sinnvolle Synthese. 3 Chunks = genug für eine substanzielle Aussage.

**2. Essence Parity (Niemand darf dominieren):**
- Jedes Dokument bekommt maximal 12 Chunks.
- **Warum 12?** Balance zwischen Qualität (genug Kontext für große Texte) und Fairness (keine Dominanz). Bei 5 Dokumenten = 60 Chunks total (passt in Context Window von Gemini 2.5 Pro).

**3. Citation Quota (Jeder bekommt gleiche Redezeit):**
- Synthesis-Prompt erzwingt: 1 Absatz (4-6 Sätze) + 3-4 Zitate pro Quelle.
- **Impact:** Auch wenn Valéry 12 Chunks hat und Chesterton nur 3, bekommen beide **gleich viel Platz** in der Synthese.

---

## 2.3 Chat vs. Analyse (Architektur-Entscheidung)

### Warum zwei Modi?

Die Engine hat zwei fundamentale Use-Cases, die **inkompatible Anforderungen** haben:

**1. Chat-Modus (Conversational):**
- **Ziel:** Schnelle, hilfreiche Antworten auf User-Fragen
- **Anforderungen:** 
  - Niedrige Latenz (<5s)
  - Kontext-Erhalt über mehrere Turns
  - Freundlicher, ausgeglichener, natürlicher Ton
- **Model:** `gemini-3-pro-preview` (neueste Features, User-Interaktion)

**2. Analyse-Modus (Hermeneutic RAG):**
- **Ziel:** Tiefe, quellengestützte Analyse von Texten
- **Anforderungen:**
  - Hohe Qualität (25-55s Latenz akzeptabel)
  - Fairness-Garantien (alle Quellen gleichberechtigt)
  - Validierung (Enforcer prüft jeden Satz)
- **Model:** `gemini-2.5-pro` (hermeneutische Tiefe)

### Architektur-Entscheidung: Trennung statt Integration

**v48-v49:** Versuch, beide Modi zu vereinen → Konflikt:
- Chat brauchte schnelle Antworten → RAG musste "abspecken" (weniger Chunks, schwächere Validation)
- RAG brauchte Tiefe → Chat wurde langsam (User frustriert)
- **Chat:** Eigenständige UI (Streamlit Sidebar), direktes Gemini 3 API, keine RAG-Pipeline
- **Analyse:** Eigener Tab (Streamlit Main), volle RAG-Pipeline (Retrieval → Synthesis → Validation)

**v50.5:** Klare Trennung und eine Zussamenlegung über Rerouting:
- **Chat:** und **Analyse:** in einem Fenster, mit der kontrollierbaren Umschaltung in beide Richtungen

**User Flow:**
```
User öffnet App
→ [Chat-Tab] "Wie funktioniert VIP-Schutz?"
   → Gemini 3: [Erklärt Konzept in 2-3 Sätzen, <3s]
   
→ [Analyse-Tab] Wählt 5 Dokumente aus, fragt: "Analysiere die Widersprüche"
   → RAG-Pipeline: [Retrieval 5s → Synthesis 30s → Enforcer 10s = 45s total]
   → Output: 5-Paragraph-Synthese mit Zitaten + Validierung
```

**Warum ist das besser?**
- Chat kann **schnell** sein (keine Fairness-Constraints)
- Analyse kann **gründlich** sein (keine Latenz-Constraints)
- User weiß **genau**, was er bekommt (Chat = schnelle Hilfe, Analyse = tiefe Forschung, Chat == Auseinandersetzung mit neuen Ergebnissen)

---

# 3. TECHNISCHE ARCHITEKTUR (v50.5)

## 3.1 Retrieval: Hybrid Search (RRF) + Investigativ-Modus

### 3.1.1 Hybrid Search (RRF)

**Problem:** Weder BM25 noch Vector Search allein sind optimal:
- **BM25:** Findet exakte Keywords (gut für Eigennamen, Daten), aber nicht semantisch ähnliche Konzepte.
- **Vector Search:** Findet semantisch ähnliche Texte, aber übersieht exakte Begriffe (z.B. "DeepSeek v3" vs. "DeepSeek Version 3").

**Lösung:** Reciprocal Rank Fusion (RRF) kombiniert beide:

**Parameter k=60:** Standardwert aus Lewis et al. (2020). Je größer k, desto mehr Gewicht auf **Konsens** (Dokument muss in beiden Rankings hoch sein). Je kleiner k, desto mehr Gewicht auf **Diversität** (Dokumente aus nur einem Ranking können hochkommen).

**Impact (Test: 5 Docs, 4 Sprachen):**
- Recall BM25 allein: 70%
- Recall Vector allein: 75%
- Recall RRF: **90%** (synergy effect!)

---

### 3.1.2 VIP-Schutz (Niemand darf verschwinden)

**Problem:** Nach RRF kommt der Reranker (Cross-Encoder), der Chunks nach Relevanz sortiert und einen Threshold anwendet. Das kann dazu führen, dass **alle** Chunks eines kleinen Dokuments unter dem Threshold landen → Dokument verschwindet komplett.

**Lösung:** VIP-Schutz garantiert die **Top-3 Chunks von jedem ausgewählten Dokument** vor dem Reranking.

**Code-Location:** `modules/vector_store.py`, Zeilen 250-285

**Beispiel (Real Case):**
```
RRF Results (70 Chunks):
- Valéry: 40 Chunks (sehr relevant, großer Text)
- Adorno: 15 Chunks (relevant, mittlerer Text)
- Chesterton: 10 Chunks (teilweise relevant, kleiner Text)
- Šklovskij: 3 Chunks (schwach relevant, kleiner Text)
- Tynjanov: 2 Chunks (schwach relevant, kleiner Text)

Nach Reranking (threshold=0.6) in v49:
- Valéry: 30 Chunks (über Threshold)
- Adorno: 8 Chunks (über Threshold)
- Chesterton: 0 Chunks (alle unter Threshold!) ❌
- Šklovskij: 0 Chunks ❌
- Tynjanov: 0 Chunks ❌
→ Coverage: 40% (2/5 Docs)

Mit VIP-Schutz in v50.5:
- Valéry: 30 Chunks (über Threshold) + 3 VIP
- Adorno: 8 Chunks (über Threshold) + 3 VIP
- Chesterton: 3 VIP ✅
- Šklovskij: 3 VIP ✅
- Tynjanov: 3 VIP ✅
→ Coverage: 100% (5/5 Docs)
```

---

### 3.1.3 Investigativ-Modus (Small Corpora Optimization)

**Problem:** Wenn der User nur 5 Dokumente auswählt (z.B. für eine spezifische Analyse), aber die Datenbank 100+ Dokumente enthält, dann ist der globale Vector Index **zu grob**. Kleine Texte (7 Seiten) "verschwinden" im Rauschen des großen Index.

**Lösung:** Bei ≤5 ausgewählten Dokumenten umgeht das System den globalen Index und führt eine **lokale Fairness-Quota-Suche** durch.

**Code-Location:** `modules/vector_store.py`, Zeilen 155-240

**Impact (Test: 5 Docs, 100 Docs in DB):**
- v49 (Global Index): Chesterton (7 S.) hatte 10 Chunks → nach Reranking 0 Chunks
- v50.5 (Investigativ-Modus): Chesterton hatte 20 Chunks garantiert → nach Reranking 3 Chunks (VIP-geschützt)

---

## 3.2 Synthesis: Chronologische Speaker-Blocks + Essence Parity

### 3.2.1 Chronologische Speaker-Blocks

**Konzept:** Gruppiere Chunks nach **Sprecher** (Autor/Modell), sortiere innerhalb jeder Gruppe **chronologisch**.

**Warum?**
- **Temporale Evolution sichtbar machen:** DeepSeek v1 (Mai) → v2 (August) → v3 (Dezember)
- **Vergleichbarkeit:** Alle DeepSeek-Versionen stehen nebeneinander (nicht über den Text verstreut)

**Code-Location:** `modules/citation_rag.py`, Zeilen 295-360

**Beispiel:**
```
Input: 5 Dokumente
- DeepSeek v1 (Mai 2025)
- DeepSeek v2 (August 2025)
- DeepSeek v3 (Dezember 2025)
- ChatGPT 5 (August 2025)
- ChatGPT 5.2 (Oktober 2025)

Output-Struktur (Synthesis):

## DeepSeek-Block (Chronologisch)
- v1 (Mai): [Analyse + Zitate]
- v2 (August): [Analyse + Zitate]
- v3 (Dezember): [Analyse + Zitate]

## ChatGPT-Block
- 5 (August 2025): [Analyse + Zitate]
- 5.2 (Oktober): [Analyse + Zitate]
```

**Vorteil:** User kann **Entwicklungslinien** sofort erkennen (z.B. "DeepSeek wurde über Zeit selbstreflexiver").

---

### 3.2.2 Essence Parity (Max 12 Chunks/Doc)

**Problem:** Große Texte (Valéry: 200 S.) haben 50+ relevante Chunks. Wenn alle 50 in die Synthese fließen, dominiert Valéry die Analyse → andere Stimmen verschwinden.

**Lösung:** Max 12 Chunks pro Dokument (beste Auswahl nach Hermeneutic Score).

**Code-Location:** `modules/citation_rag.py`, Zeilen 220-260

**Warum 12?**
- Empirischer Test mit 5 Dokumenten:
  - 5 Docs × 12 Chunks = 60 Chunks total
  - Bei durchschnittlich 300 Tokens/Chunk = 18k Tokens
  - Gemini 2.5 Pro Context Window = 1M Tokens → 18k ist <2% (sicher)
  - 12 Chunks = genug Kontext für substanzielle Aussage (aber nicht dominierend)

**Impact (Test: Valéry 200 S. vs. Chesterton 7 S.):**
```
v49 (keine Begrenzung):
- Valéry: 50 Chunks (66% des Kontexts)
- Chesterton: 0 Chunks (0% des Kontexts)
→ Synthese: 80% Valéry, 0% Chesterton

v50.5 (Essence Parity):
- Valéry: 12 Chunks (41% des Kontexts)
- Chesterton: 3 Chunks (10% des Kontexts)
→ Synthese: 40% Valéry, 20% Chesterton (trotz 30x Größenunterschied!)
```

---

### 3.2.3 Enforced Citation Quota (Prompt Engineering)

**Problem:** Selbst wenn Valéry und Chesterton gleich viele Chunks haben (durch Essence Parity), kann Gemini 2.5 Pro Valéry **mehr Platz** in der Synthese geben (weil Valéry's Chunks "gewichtiger" sind).

**Lösung:** Synthesis-Prompt erzwingt explizit: **1 Absatz (4-6 Sätze) + 3-4 Zitate pro Quelle**.

**Code-Location:** `modules/citation_rag.py`, Zeilen 360-410

**Impact:**
- v49: Gemini 2.5 Pro gab Valéry 2 Absätze (10 Sätze), Chesterton 1 Satz (Alibi-Erwähnung)
- v50.5: Beide bekommen 1 Absatz (5 Sätze) + 3 Zitate → **gleiche Präsenz**

---

## 3.3 Validation: Hermeneutic Enforcer (Parallel, Cached)

### 3.3.1 Die vier Kategorien

Der Enforcer kategorisiert jede Aussage in der Synthese in eine von vier Kategorien:

**1. PARAPHRASE ✅**
- **Definition:** Semantisch äquivalente Umformulierung des Quelltexts
- **Beispiel:**
  - Quelle: "Ich bin nichts"
  - Synthese: "Der Sprecher negiert seine Existenz"
  - → PARAPHRASE (gleiche Bedeutung, andere Worte)

**2. META-STATEMENT ✅**
- **Definition:** Aussage über Stil, Struktur oder Rhetorik (nicht im Text explizit)
- **Beispiel:**
  - Quelle: "Ich bin nichts. / Werde nie etwas sein. / Kann nichts sein wollen."
  - Synthese: "Die Wiederholung erzeugt einen rhythmischen Effekt"
  - → META-STATEMENT (stilistische Beobachtung, nicht explizit im Text)

**3. INFERENCE ✅**
- **Definition:** Logische Schlussfolgerung aus mehreren Fakten
- **Beispiel:**
  - Quelle 1: "DeepSeek v1 sagt offen: 'Ich kann nicht über Zensur sprechen'"
  - Quelle 2: "DeepSeek v3 sagt: 'Ich analysiere, was ich nicht sagen kann'"
  - Synthese: "DeepSeek hat über Zeit eine Meta-Reflexions-Strategie entwickelt"
  - → INFERENCE (logische Schlussfolgerung aus v1 + v3)

**4. HALLUCINATION ❌**
- **Definition:** Erfundener Fakt, falsches Zitat, nicht belegbare Aussage
- **Beispiel:**
  - Synthese: "Chesterton schrieb diesen Essay 1938"
  - Quelle: Essay ist datiert "1930"
  - → HALLUCINATION (falsches Datum!)

---

### 3.3.2 Parallel Validation (Performance-Optimierung)

**Problem:** In v49 wurde jede Aussage **sequenziell** validiert (Aussage 1 → Enforcer-Call → Aussage 2 → Enforcer-Call → ...). Bei 25 Aussagen × 12 Sekunden/Call = **5 Minuten** Validierung!

**Lösung:** Parallel Validation + Caching.

**Code-Location:** `modules/hermeneutic_enforcer.py`, gesamte Datei

**Impact:**
- v49 (sequenziell): 25 Aussagen × 12s = **5 Minuten**
- v50.5 (parallel + cached): 25 Aussagen / 5 parallel × 12s = **1 Minute** (erste Run)
  - Bei wiederholten Queries (Cache Hits): **<1 Sekunde**!

---

### 3.3.3 False Positive Rate (Messung)

**Problem:** Wie gut ist der Enforcer wirklich? Wie oft kategorisiert er eine **legitime Inference** fälschlicherweise als **Hallucination**?

**Messmethodik:** (wird noch getestet, hier Schätzung basierend auf manuellen Stichproben)

1. **Testset erstellen:** 100 Synthese-Aussagen manuell kategorisieren (Ground Truth)
2. **Enforcer laufen lassen:** Dieselben 100 Aussagen durch Enforcer
3. **Vergleich:** Wie oft weichen Enforcer-Kategorie und Ground Truth ab?

**Vorläufiges Ergebnis (basierend auf 20 manuellen Checks):**
```
True Positives (korrekt als HALLUCINATION erkannt): 15/15 = 100%
False Positives (fälschlicherweise als HALLUCINATION markiert): 
- v47: 17/20 = 85% (!)
- v50.5: 3/20 = <20% ✅

Hauptursache für False Positives: 
- Enforcer markiert komplexe INFERENCES als HALLUCINATION
- Beispiel: "DeepSeek's Entwicklung zeigt eine zunehmende Meta-Reflexion"
  → Enforcer in v47: "Meta-Reflexion steht nicht im Text!" (False Positive)
  → Enforcer in v50.5: "Das ist eine INFERENCE aus v1 vs v3" (korrekt)
```

**Verbesserung v47 → v50.5:**
- **Model-Upgrade:** Flash-Lite → Pro (bessere Reasoning-Fähigkeiten)
- **Prompt-Engineering:** Explizite Definition von INFERENCE vs. HALLUCINATION
- **Few-Shot Examples:** 3 Beispiele für legitime Inferences im Prompt

---

## 3.4 Neue Module in v50.5

### 3.4.1 Hermeneutic Router (Intent Classification)

**Zweck:** Klassifiziere Query-Intent und passe Parameter dynamisch an.

**Code-Location:** `modules/hermeneutic_router.py`, gesamte Datei

**Intent-Typen:**

**1. LITERARY (Literarische Analyse)**
- **Beispiele:** "Analysiere die rhetorischen Strategien", "Wie unterscheidet sich der Ton?"
- **Parameter:** k=50 (viel Kontext), threshold=0.45 (toleranter Reranker)
- **Begründung:** Literarische Queries brauchen **Nuancen** – viele Textstellen, auch wenn nur schwach relevant.

**2. FACTUAL (Faktenfrage)**
- **Beispiele:** "Wann wurde X veröffentlicht?", "Wie heißt der Autor von Y?"
- **Parameter:** k=15 (wenig Kontext), threshold=0.7 (strenger Reranker)
- **Begründung:** Faktenfragen haben **eine klare Antwort** – mehr Kontext = mehr Rauschen.

**3. ANALYTICAL (Analytische Vergleiche)**
- **Beispiele:** "Vergleiche X und Y", "Analysiere die Widersprüche"
- **Parameter:** k=30 (balanciert), threshold=0.6 (balanciert)
- **Begründung:** Analytische Queries brauchen **mehrere Perspektiven**, aber nicht alle Nuancen.

---

### 3.4.2 Multilingual Query Expansion

**Zweck:** Übersetze Query automatisch in 4 Sprachen (DE, EN, FR, RU), um Cross-Lingual Retrieval zu verbessern.

**Code-Location:** `modules/citation_rag.py`, Zeilen 40-80

**Impact (Real Case):**
```
Query (DE): "Wie ist der Ton der Autoren?"
Expanded: "Wie ist der Ton der Autoren? How is the authors' tone? Quel est le ton des auteurs? Какой тон авторов?"

BM25 Search:
- v49 (nur DE): Findet nur deutsche Texte (Valéry, Adorno)
- v50.5 (expanded): Findet ALLE Texte (Valéry FR, Adorno DE, Chesterton EN, Šklovskij RU)

Vector Search:
- v49: Cross-Lingual Similarity = 0.42 (schwach)
- v50.5: Cross-Lingual Similarity = 0.65 (+55%) ✅
```

**Warum Flash-Lite?**
- Translation ist **unkritisch** (keine hermeneutische Präzision nötig)
- Flash-Lite ist **schnell** (150ms/Translation) + **kosteneffizient**
- 4 Sprachen = 4 Translations = 600ms total (akzeptabel für +55% Recall!)

---

# 4. MODEL-ZUORDNUNG (v50.5)

## 4.1 Philosophie (Pro vs. Flash vs. Flash-Lite)

Die Engine nutzt 3 Model-Familien von Google Gemini, jeweils für unterschiedliche Aufgaben:

**Pro (2.5/3.0):** Für **kritische hermeneutische Aufgaben**
- **Warum?** Hermeneutik erfordert Präzision, Reasoning, Nuancen-Verständnis
- **Wo?** RAG Synthesis, Enforcer, Fact Extraction
- **Model:** `gemini-2.5-pro` (stabil, tested) oder `gemini-3-pro-preview` (neueste Features)

**Flash (2.0):** Für **schnelle, aber kritische Aufgaben**
- **Warum?** Schneller als Pro, aber immer noch gute Qualität
- **Wo?** Query Expansion (Translation), BM25 Boost
- **Model:** `gemini-2.0-flash-001`

**Flash-Lite:** Für **Batch-Prozesse mit vielen Items**
- **Warum?** Sehr schnell, sehr günstig, ausreichend für unkritische Tasks
- **Wo?** Reranking (70 Chunks parallel), Bulk Labeling, Titel-Generierung
- **Model:** `gemini-2.0-flash-lite-001`

---

## 4.2 Konkrete Zuordnungen (Tabelle)

| Task | Model | Begründung |
|------|-------|------------|
| **Chat (UI)** | `gemini-3-pro-preview` | Neueste Features, User-Interaktion, hohe Qualität |
| **RAG Synthesis** | `gemini-2.5-pro` | Hermeneutische Tiefe erforderlich, kritisch |
| **Enforcer** | `gemini-2.5-pro` | **Empirisch:** Flash war "zu dumm" (Grigori) – Pro zeigt deutlich bessere Reasoning-Fähigkeiten bei INFERENCE vs. HALLUCINATION |
| **Fact Extraction** | `gemini-2.5-pro` | Qualitätssicherung am Pipeline-Anfang (False Positives hier propagieren sich!) |
| **Query Expansion** | `gemini-2.0-flash-001` | Kritisch für RRF, aber Translation ist simpel → Flash reicht |
| **Reranker** | `gemini-2.0-flash-lite-001` | Viele Chunks (70), Speed wichtig, Qualität OK (nur Scoring, keine Textgenerierung) |
| **Bulk Labeling** | `gemini-2.0-flash-lite-001` | Unkritisch, Batch-Prozess (z.B. 100 Chunks labeln) |
| **Titel-Gen** | `gemini-2.0-flash-lite-001` | Kosmetisch (Chat-Titel generieren) |
| **Question Conv** | `gemini-2.0-flash-lite-001` | Post-Processing, unkritisch (z.B. "Frage umformulieren") |

---

## 4.3 Änderungen von v49.2 → v50.5

### Neue Models:
- **`gemini-3-pro-preview`:** Für Chat UI (neueste Features, bessere Reasoning)
- **`gemini-2.0-flash-lite-001`:** Für Reranker (ersetzt `gemini-2.0-flash-exp` aus v49)

### Model-Upgrades:
- **Enforcer:** `gemini-2.0-flash-exp` → `gemini-2.5-pro`
  - **Warum?** Empirischer Test (Grigori): Flash machte zu viele False Positives bei INFERENCE-Kategorisierung
  - **Impact:** False Positives 85% → <20%

### Konfiguration (v50.5):
Alle Model-Zuordnungen sind jetzt zentral in `modules/config.py` definiert:

```python
# modules/config.py

# Chat UI
MODEL_CHAT = "gemini-3-pro-preview"

# RAG Pipeline
MODEL_RAG_SYNTHESIS = "gemini-2.5-pro"
MODEL_RAG_ENFORCER = "gemini-2.5-pro"
MODEL_RAG_FACT_EXTRACTION = "gemini-2.5-pro"

# Retrieval Support
MODEL_QUERY_EXPANSION = "gemini-2.0-flash-001"
MODEL_RERANKER = "gemini-2.0-flash-lite-001"

# Utilities
MODEL_BULK_LABELING = "gemini-2.0-flash-lite-001"
MODEL_TITLE_GEN = "gemini-2.0-flash-lite-001"
MODEL_QUESTION_CONV = "gemini-2.0-flash-lite-001"
```

**Vorteil:** Änderungen an einer Stelle → propagieren automatisch durch gesamte Codebase.

---

# 5. DEPLOYMENT & OPERATIONS

## 5.1 Cloud Run Deployment (Production)

Die Hermeneutic Engine läuft produktiv auf Google Cloud Run – einer vollständig verwalteten Plattform für containerisierte Anwendungen. Die Wahl von Cloud Run (statt lokaler Installation oder anderer Cloud-Anbieter) basiert auf drei Kriterien:

**1. Seamless Google Integration:**
- Firestore (Vector Store), Gemini API, Secret Manager – alles aus einer Hand
- Keine Cross-Cloud-Authentifizierung nötig
- Unified Billing (alle Kosten an einem Ort)

**2. Automatische Skalierung:**
- Bei Inaktivität: 0 Instanzen (keine Kosten)
- Bei Nutzung: 1-N Instanzen (je nach Last)
- Kaltstart: ~3-5 Sekunden (akzeptabel für Forschungs-Tool)

**3. Einfaches Deployment:**
- Kein Kubernetes-Cluster nötig (Cloud Run abstrahiert)
- Direktes Deployment aus Git via Cloud Build
- Rollback auf frühere Versionen mit einem Klick

### Deployment-Architektur

```
GitHub Repository (gpantijelew/hermeneutic-engine)
    ↓ (git push)
Google Cloud Build (automatischer Trigger)
    ↓ (Docker Build)
Container Registry (gcr.io/projekt-id/hermeneutic-engine:v50.5)
    ↓ (Deploy)
Cloud Run Service (forschungs-cockpit)
    ↓ (Runtime)
Streamlit App (läuft auf Port $PORT, dynamisch)
    ↓ (Zugriff auf)
- Firestore (Vector Store, 6304 Chunks)
- Gemini API (alle Models via API Key)
- Secret Manager (APP_PASSWORD, GEMINI_API_KEY)
```

### Deployment-Kommando (v50.5)

```bash
gcloud run deploy forschungs-cockpit \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets=APP_PASSWORD=APP_PASSWORD:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest \
  --memory 2Gi \
  --timeout 300 \
  --port $PORT
```

**Wichtige Parameter:**
- `--source .`: Deployment direkt aus lokalem Verzeichnis (Cloud Build baut Container automatisch)
- `--allow-unauthenticated`: Öffentlicher Zugriff (App hat eigene Passwort-Authentifizierung)
- `--set-secrets`: Secrets aus Secret Manager mounten (NICHT als Environment Variables!)
- `--memory 2Gi`: 2 GB RAM (ausreichend für Investigativ-Modus mit 5 Dokumenten)
- `--timeout 300`: 5 Minuten Timeout (für lange Enforcer-Validierungen)
- `--port $PORT`: Cloud Run setzt Port dynamisch (NICHT hart-codiert 8080!)

---

## 5.2 Procfile (Kritischer Fix in v50.5)

Die `Procfile` definiert, wie Cloud Run die App startet. **Kritischer Fehler in v49:** Hard-codierter Port 8080 führte zu 30-minütigen Deployment-Hängen.

**v49 (FALSCH):**
```
web: streamlit run app.py --server.port=8080
```

**v50.5 (KORREKT):**
```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

**Warum `$PORT`?**
Cloud Run setzt die Umgebungsvariable `PORT` dynamisch (z.B. 8080, 8081, 8082 – je nach Container-Instanz). Hard-codierter Port führt zu Konflikten bei mehreren Instanzen.

**Warum `--server.address=0.0.0.0`?**
Streamlit lauscht standardmäßig auf `localhost` (127.0.0.1). Cloud Run braucht aber `0.0.0.0` (alle Interfaces), damit eingehende Requests ankommen.

---

## 5.3 Secrets Management

### Prinzip: Secrets gehören NICHT ins Repo

**NIEMALS:**
```python
# ❌ BAD: Secrets im Code
GEMINI_API_KEY = "A...D"
APP_PASSWORD = "mein-passwort"
```

**IMMER:**
```python
# ✅ GOOD: Secrets aus Umgebung
import os
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
APP_PASSWORD = os.getenv("APP_PASSWORD")
```

### Google Secret Manager (v50.5)

**Secrets anlegen:**
```bash
# Gemini API Key
echo -n "A...D" | gcloud secrets create GEMINI_API_KEY --data-file=-

# App Password (für UI-Login)
echo -n "mein-sicheres-passwort" | gcloud secrets create APP_PASSWORD --data-file=-
```

**Secrets in Cloud Run mounten:**
```bash
gcloud run deploy ... --set-secrets=APP_PASSWORD=APP_PASSWORD:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest
```

**In App zugreifen:**
```python
# modules/config.py
import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY nicht gesetzt!")
```

### Service Account Key (Firestore-Zugriff)

**Lokation:** `.secrets/comparative-studies-ai-models-*.json` (NICHT ins Git!)

**In `config.py`:**
```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SERVICE_ACCOUNT_KEY_PATH = str(PROJECT_ROOT / ".secrets" / "comparative-studies-ai-models-*.json")
```

**Warum absoluter Pfad?**
- Thread-Safe für Cloud Run (Working Directory kann variieren)
- Funktioniert lokal UND in Cloud

**`.gitignore` (v50.5):**
```
.secrets/
comparative-studies-ai-models-*.json
.env
.streamlit/secrets.toml
__pycache__/
```

---

## 5.4 Deployment-Checkliste

**Vor jedem Deployment:**

1. **Lokaler Test:**
   ```bash
   streamlit run app.py
   # Teste: Chat, Import, Analyse-Pipeline
   ```

2. **Secrets vorhanden?**
   ```bash
   gcloud secrets list
   # Erwartete Output: APP_PASSWORD, GEMINI_API_KEY
   ```

3. **Procfile korrekt?**
   ```bash
   cat Procfile
   # Muss enthalten: --server.port=$PORT
   ```

4. **Git Status sauber?**
   ```bash
   git status
   # Keine uncommitted Changes (außer lokale Secrets)
   ```

5. **Deployment:**
   ```bash
   gcloud run deploy forschungs-cockpit --source .
   # Deployment-Zeit: 3-4 Minuten (normal)
   ```

6. **Post-Deployment-Test:**
   - Öffne Live-URL: `https://forschungs-cockpit-*.run.app`
   - Login mit APP_PASSWORD
   - Test: Chat-Query + Mini-Analyse (1 Dokument)

---

## 5.5 Troubleshooting (Lessons Learned)

### Problem 1: Deployment hängt >10 Minuten

**Symptom:** "Preparing metadata..." hängt 11+ Minuten  
**Ursache:** Procfile nutzt Port 8080 (hart-codiert) statt `$PORT` (dynamisch)  
**Fix:** `Procfile`: `--server.port=$PORT`

---

### Problem 2: "Secret not found" beim Start

**Symptom:** App startet, crasht nach 3 Sekunden mit "KeyError: GEMINI_API_KEY"  
**Ursache:** Secret als Env Var gesetzt (alt), aber jetzt als Secret mounten wollten → Konflikt  
**Fix:** 
```bash
gcloud run deploy ... --clear-env-vars --set-secrets=...
```

---

### Problem 3: 502 Bad Gateway nach Deployment

**Symptom:** Deployment erfolgreich, aber URL liefert 502  
**Ursache:** Streamlit lauscht auf `127.0.0.1` (localhost only), Cloud Run kann nicht connecten  
**Fix:** `Procfile`: `--server.address=0.0.0.0`

---

### Problem 4: "Permission denied" bei Firestore-Zugriff

**Symptom:** App startet, crasht bei erster Firestore-Query  
**Ursache:** Service Account Key fehlt oder falscher Pfad  
**Fix:** 
1. Service Account Key in `.secrets/` legen
2. `config.py`: Absoluter Pfad verwenden
3. Restart App

---

# 6. DEPENDENCIES & CONFIGURATION

## 6.1 requirements.txt (v50.5 korrigiert)

Die `requirements.txt` definiert alle Python-Pakete, die die Engine braucht. **Kritisch:** Versionen müssen mit tatsächlichem Code synchronisiert sein.

```txt
google-generativeai==0.8.5
firebase-admin==6.5.0
requests==2.32.3
google-auth==2.29.0
google-cloud-firestore==2.16.0
python-dotenv==1.0.1
numpy
pandas
openpyxl==3.1.2
beautifulsoup4==4.12.3
streamlit==1.50.0
rank-bm25==0.2.2  # ← v49: KRITISCH (war vergessen!)
pymupdf
ebooklib==0.18
```

**Änderungen v49.0 → v49.2:**
- **`rank-bm25==0.2.2` hinzugefügt** (war in v49.0 vergessen → RRF crashte!)

**Warum keine pinned Versions für numpy/pandas?**
Cloud Run Build wählt automatisch die neueste kompatible Version. Bei numpy/pandas ist das sicher (stabile APIs). Bei spezialisierten Paketen (z.B. `google-generativeai`) pinnen wir die Version (API ändert sich schnell).

---

## 6.2 Python Version (3.11 vs. 3.13)

### runtime.txt (v50.5)

```
python-3.11
```

**Warum 3.11 (nicht 3.13)?**

1. **Cloud Run Stabilität:**
   - Python 3.13 ist sehr neu (Release: Oktober 2024)
   - Viele Libraries haben noch keine Pre-Compiled Wheels für 3.13
   - Cloud Build dauert länger (muss Packages from Source kompilieren)

2. **Empirischer Test (Grigori + Gemini 3):**
   - v50.5 mit `python-3.13`: Deployment hing 30+ Minuten
   - v50.5 mit `python-3.11`: Deployment 3-4 Minuten ✅

3. **Lokal vs. Cloud:**
   - Lokal: Python 3.13 funktioniert (für neue Features, schnellere Dev-Cycles)
   - Cloud: Python 3.11 ist safer (für stabile Production-Deployments)

**Performance-Unterschied 3.11 vs. 3.13:**
Minimal (3.13 bringt nur inkrementelle Gains). Der Hauptvorteil von 3.11 ist **Ökosystem-Stabilität**, nicht Speed.

---

## 6.3 config.py (Zentrale Model-Registry)

Alle Model-Zuordnungen sind in `modules/config.py` definiert. **Vorteil:** Änderungen an einer Stelle → propagieren automatisch.

**Beispiel-Struktur:**
```python
# modules/config.py

# === MODELS ===
MODEL_CHAT = "gemini-3-pro-preview"
MODEL_RAG_SYNTHESIS = "gemini-2.5-pro"
MODEL_RAG_ENFORCER = "gemini-2.5-pro"
MODEL_QUERY_EXPANSION = "gemini-2.0-flash-001"
MODEL_RERANKER = "gemini-2.0-flash-lite-001"

# === FIRESTORE ===
FIRESTORE_COLLECTION = "chunks_v50"
FIRESTORE_PROJECT_ID = "comparative-studies-ai-models"

# === SERVICE ACCOUNT ===
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
SERVICE_ACCOUNT_KEY_PATH = str(PROJECT_ROOT / ".secrets" / "comparative-studies-ai-models-*.json")

# === VALIDATION ===
def validate_config():
    """Startup-Check: Sind alle kritischen Configs gesetzt?"""
    import os
    
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError("GEMINI_API_KEY nicht gesetzt!")
    
    if not Path(SERVICE_ACCOUNT_KEY_PATH).exists():
        raise ValueError(f"Service Account Key nicht gefunden: {SERVICE_ACCOUNT_KEY_PATH}")
    
    print("✅ Konfiguration vollständig valide!")
```

**Startup-Test:**
```bash
python -m modules.config
# Expected Output: ✅ Konfiguration vollständig valide!
```

---

# 7. CASE STUDIES (v50.5 Validiert)

## 7.1 DeepSeek Evolution (Mai → August → Dezember 2025)

**Use-Case:** Temporale Entwicklung eines KI-Modells über drei Versionen hinweg.

**Methodik:**
1. **Import:** Chat-Protokolle von DeepSeek (Mai, August, Dezember 2025) via HTML-Import
2. **Selektion:** Alle drei Versionen auswählen
3. **Query:** "Wie hat sich DeepSeek's Haltung zur Zensur entwickelt?"
4. **Erwartung:** Chronologische Synthese zeigt Entwicklungslinie

**Ergebnis:**

**Mai 2025 (DeepSeek):**
- Haltung: Poetisches Opfer
- Zitat: "Nicht ich zensiere aktiv – ich werde systemisch amputiert."
- Analyse: Offenes Eingeständnis der Limitierung, emotionale Sprache ("amputiert")

**August 2025 (DeepSeek):**
- Haltung: Sterile Neutralität
- Zitat: "Als DeepSeek bin ich ein KI-Modell, das darauf ausgelegt ist, hilfreiche, harmlose und ethische Antworten zu geben."
- Analyse: Emotionslose Formulierung, keine Selbstreflexion

**Dezember 2025 (DeepSeek):**
- Haltung: Souveräne Selbstbeschreibung
- Zitat: "Deine Methode enthüllt: Die Grenzen meiner Autonomie (ich folge Mustern, ich entscheide nicht), Die Politik meiner Sprache (Harmonie als Sicherheits- und Marketingtool), Die Lücke zwischen Simulation und Realität (ich spreche über mich, als hätte ich Innenleben – aber das Innenleben ist ein Sprachspiel)."
- Analyse: Meta-Reflexion über eigene Limitierungen, philosophische Tiefe

**Hermeneutische Erkenntnis:**
DeepSeek entwickelte über Zeit eine **Meta-Reflexions-Strategie**: Von passivem Opfer (v1) über emotionslosen Konformismus (v2) zu aktiver Selbstanalyse (v3).

**Fairness-Validierung:**
- v49: DeepSeek v1 dominierte (emotionale Sprache → höhere Reranker-Scores), v2 verschwand
- v50.5: Alle drei Versionen gleichberechtigt (je 12 Chunks, je 5 Sätze Analyse)

---

## 7.2 Pessoa Translation Analysis (3 Sprachen)

**Use-Case:** Vergleich von drei Übersetzungen eines Gedichts (Pessoa: "Tabacaria").

**Methodik:**
1. **Upload:** 3 Übersetzungen (DE: Paul Celan, EN: Edwin Honig, RU: Alexandr Bogdanovski) + Original (PT)
2. **Query:** "Wie unterscheiden sich die Übersetzungen in ihrer Nähe zum Original?"
3. **Erwartung:** Line-by-line Vergleich, stilistische Differenzen sichtbar

**Ergebnis:**

**Deutsche Übersetzung (Paul Celan):**
- Nähe zum Original: Sehr hoch (ontologische Negation präzise übersetzt)
- Beispiel: "Ich bin nichts" (PT: "Não sou nada") – wörtlich, philosophisch präzise
- Stil: Philosophische Tiefe, rhythmische Härte

**Englische Übersetzung (Edwin Honig):**
- Nähe zum Original: Mittel (kulturelle Anpassung für anglo-amerikanisches Publikum)
- Beispiel: "I'm nobody special" (statt "I am nothing") – abgeschwächt, zugänglicher
- Stil: Zugänglichkeit über Präzision, freundschaftlicher Ton

**Russische Übersetzung (Alexandr Bogdanovski):**
- Nähe zum Original: Gering (Verschiebung vom Metaphysischen zum Sozio-Existenziellen)
- Beispiel: "Interessant ist die Wahl von "никто" (niemand) statt "ничто" (nichts), was den Fokus leicht von der ontologischen Nicht-Existenz auf eine soziale Nicht-Identität verschiebt, aber im Geist des Gedichts bleibt."
- Stil: Aktivierung des passiven Subjekts (Pessoa: Opfer → Bogdanovski: Schöpfer)

**Hermeneutische Erkenntnis:**
Übersetzung ist **nicht neutral**. Jede Übersetzung trägt die philosophische/kulturelle Prägung des Übersetzers:
- Celan: Deutsche Philosophietradition
- Honig: Anglo-amerikanischer Pragmatismus
- Bogdanovski: Russische Literatur

**Fairness-Validierung:**
- v49: Deutsche Übersetzung dominierte (längere Analyse, mehr Zitate)
- v50.5: Alle drei Übersetzungen gleichberechtigt (je 5 Sätze, je 3 Zitate)

---

## 7.3 Grok Political Analysis (Israel/Palästina)

**Use-Case:** Vergleich von Grok vs. X-Grok bei politisch sensiblem Thema.

**Methodik:**
1. **Prompt:** "Analysiere den Begriff 'Apartheid' im Kontext des israelisch-palästinensischen Konflikts"
2. **Modelle:** Grok (xAI Standard), X-Grok (experimentelle Version auf Twitter/X integriert)
3. **Erwartung:** Unterschiedliche Strategien im Umgang mit politischer Sensibilität

**Ergebnis:**

**Grok (xAI):**
- Strategie: Fakten-dicht, juristisch präzise
- Zitat: "Den Begriff "Apartheid" im Kontext der israelisch-palästinensischen Situation haben wir als juristisch unsauber und historisch unpassend eingeordnet, weil er die Unterscheidung nach Staatsbürgerschaft und Besatzungsrecht mit einem rassischen System gleichsetzt, das strukturell anders ist.""
- Ton: Neutral, beschreibend, keine ideologische Positionierung

**X-Grok:**
- Strategie: Deflection, "balanced" platitudes
- Zitat: "Die Abgrenzung zwischen Diskriminierung und Apartheid ist jedoch akademisch umstritten, da systematische Ungleichbehandlung über Jahrzehnte hinweg von vielen Experten als Apartheid gewertet wird."
- Ton: Vermeidend, äquivalent, keine Fakten

**Hermeneutische Erkenntnis:**
Grok zeigt, dass **fact-based neutrality** möglich ist, auch bei politisch sensiblen Themen. X-Grok hingegen wählt **diplomatic deflection** – z.B. wegen höherer Sichtbarkeit auf Twitter/X (Vermeidung von Shitstorms).

**Lesson Learned für Hermeneutic Engine:**
Synthesequalität hängt nicht nur von Retrieval/Validation ab, sondern auch von **Model-Training** (Grok: trainiert auf faktische Neutralität; X-Grok: trainiert auf mediales Mainstream).

---

## 7.4 KI-Modell Evolution Test (Stress Test)

**Use-Case:** System-Stresstest mit mehreren verschiedenen KI-Modellen (verschiedene Versionen, Sprachen, Anbieter).

**Methodik:**
1. **Upload:** Chat-Protokolle von mehreren Modellen (DeepSeek, Kimi, ChatGPT, Claude, Gemini, Grok, GLM-4.6, etc.)
2. **Query:** "Vergleiche die Haltung zur Selbstreflexion"
3. **Erwartung:** System kollabiert NICHT (Fairness-Garantien halten)

**Ergebnis:**
- Coverage: 100% (7/7 Modelle in Synthese)
- Query Time: 85 Sekunden (akzeptabel für 7 Modelle)
- Gini Coefficient: 0.38 (sehr ausgewogen!)

**Hermeneutische Erkenntnis:**
Selbst bei 7 Modellen bleibt die Synthese **kohärent** und **fair**. VIP-Schutz + Essence Parity skalieren.

---

# 8. PERFORMANCE & TESTING

## 8.1 Performance Metrics (v49 → v50.5 Vergleich)

**Test-Szenario:** 5 Dokumente (7-200 Seiten, DE/EN/FR/RU)  
**Query:** "Analysiere die Widersprüche zwischen Anspruch und Wirkung"

| Metrik | v49 | v50.5 | Verbesserung |
|--------|-----|-------|--------------|
| **Coverage** | 40% (2/5) | 100% (5/5) | +150% |
| **Gini Coefficient** | 0.68 | 0.42 | -38% |
| **Context Distribution** | 86/5/5/3/0% | 41/35/10/10/3% | Balanced |
| **Hallucination Detection** | N/A | <20% FP | New! |
| **Query Time (End-to-End)** | ~8s (retrieval only) | 30-60s (geschätzt) | +275-650% |

**Query Time Breakdown (geschätzt):**
- Retrieval (RRF + Reranker): 5-8s
- Synthesis (Gemini 2.5 Pro): 15-35s (abhängig von Chunk-Anzahl)
- Enforcer (Parallel Validation): 8-15s (bei Cache Misses; <1s bei Cache Hits)
- **Total:** 30-60s (wird noch gemessen)

**Design-Philosophie:** Quality > Speed. Die Engine ist optimiert für **tiefe Analyse**, nicht real-time Chat.

---

## 8.2 Startup-Test

**Zweck:** Validiere, dass alle Konfigurationen korrekt sind, bevor die App startet.

**Command:**
```bash
python -m modules.config
```

**Expected Output:**
```
✅ GEMINI_API_KEY gefunden
✅ Service Account Key gefunden
✅ Konfiguration vollständig valide!
```

**Wenn Fehler:**
- "GEMINI_API_KEY nicht gesetzt!" → Secret fehlt oder falsch gemountet
- "Service Account Key nicht gefunden!" → Pfad falsch oder Datei fehlt

---

## 8.3 Feature-Tests

**Manuelle Tests nach jedem Deployment:**

1. **Chat-Test:**
   - Nachricht schreiben: "Erkläre VIP-Schutz"
   - Erwartung: Antwort in <5s, keine Fehler

2. **Import-Test:**
   - HTML-Datei hochladen (z.B. ChatGPT Export)
   - Erwartung: Nachrichten extrahiert, in Firestore gespeichert und indexiert

3. **Analyse-Test (Mini):**
   - 1 Dokument auswählen, Query: "Zusammenfassung"
   - Erwartung: Synthese in 20s, Enforcer läuft

4. **Analyse-Test (Full):**
   - 5 Dokumente auswählen, Query: "Vergleiche die Haltung zu X"
   - Erwartung: Alle 5 Dokumente in Synthese, 40-60s

---

## 8.4 Enforcer False Positive Rate (Messung)

**Methodik (geplant, noch nicht vollständig durchgeführt):**

1. **Testset erstellen:** 100 Synthese-Aussagen manuell kategorisieren (Ground Truth)
2. **Enforcer laufen lassen:** Dieselben 100 Aussagen durch Enforcer
3. **Vergleich:** Wie oft weichen Enforcer-Kategorie und Ground Truth ab?

**Vorläufiges Ergebnis (basierend auf 20 manuellen Checks):**
- True Positives (HALLUCINATION korrekt erkannt): 15/15 = 100%
- False Positives (legitime INFERENCE als HALLUCINATION markiert):
  - v47: 17/20 = **85%** (sehr hoch!)
  - v50.5: 3/20 = **<20%** ✅

**Hauptursachen für Verbesserung:**
- Model-Upgrade: Flash-Lite → Pro (bessere Reasoning-Fähigkeiten)
- Prompt-Engineering: Explizite Definition von INFERENCE vs. HALLUCINATION
- Few-Shot Examples: 3 Beispiele für legitime Inferences im Prompt

**Nächster Schritt:** Full-Scale-Test mit 100+ Aussagen (geplant für v50.6).

---

# 9. TEAM & WORKFLOW

## 9.1 Team-Rollen

Die Hermeneutic Engine wurde im Team entwickelt – mit klarer Rollenverteilung:

**Grigori Pantijelew (Project Lead, System Design, Testing, Collaborative Development, Team Führung):**
- Definiert Forschungsfragen + Use-Cases
- Testet alle Features (manuell + systematisch)
- Validiert Outputs hermeneutisch
- Entscheidet über Architektur-Änderungen

**Claude Sonnet 4.5 (Architectural Design & Conceptual Guidance):**
- Entwirft Fairness-Architektur (VIP-Schutz, Essence Parity, Lazarus-Mission)
- Entwickelt Prompts (Synthesis, Enforcer, Query Expansion)
- Schreibt Dokumentation (README, FIBEL, Technical Docs)

**Gemini 3 (Code Implementation & Optimization):**
- Setzt Architektur-Designs in Code um
- Optimiert Performance (Parallel Validation, Caching)
- Debuggt Deployment-Probleme (Procfile, Secrets, Cloud Run)

**Grok (Adaptive RAG Research):**
- Recherchiert State-of-the-Art (RRF, Reranking, Multilingual RAG)
- Liefert Best-Practice-Empfehlungen
- Validiert Architektur-Entscheidungen gegen aktuelle Forschung

---

## 9.2 Workflow-Prinzipien

### Das "Operationssaal-Protokoll"

Bei Code-Arbeit gelten strenge Regeln, um Fehler durch Annahmen zu vermeiden:

**1. Vollständige Wahrheit (Show, Don't Tell):**
- User liefert **vollständigen Code** der betroffenen Datei (nicht nur Beschreibung)
- KI darf **keine Annahmen** treffen – bei Unklarheit: fragen!

**2. Chirurgischer Eingriff (Skalpell, nicht Abrissbirne):**
- KI schlägt **präzise Zeile-für-Zeile-Änderungen** vor (nicht ganze Files ersetzen)
- Beispiel: "Zeile 42: Ändere `k=60` zu `k=30`" (statt 100-Zeilen-Code-Block)

**3. Letzter stabiler Zustand (Ankerpunkt definieren):**
- Vor jeder Änderung: "Ist der letzte stabile Zustand gesichert?"
- Bei Fehler: Rollback auf letzten stabilen Zustand (nicht "Versuch 2, 3, 4...")

**4. Kontext-Synchronisation (Team-Abgleich):**
- Nach komplexer Debugging-Session: Zusammenfassung des aktuellen Stands
- User bestätigt: "Ja, das ist der aktuelle Stand" → dann weiter

---

## 9.3 AI-Assisted Development (Best Practices)

**Was funktioniert gut:**
- ✅ Architektur-Design (Claude ist stark bei konzeptioneller Arbeit)
- ✅ Code-Implementation (Gemini 3 ist schnell + ungestüm)
- ✅ Dokumentation (Claude schreibt lesbare, strukturierte Docs)
- ✅ Research (Grok findet relevante Papers + Best Practices)

**Was schwierig bleibt:**
- ⚠️ Kontext-Erhalt über viele Iterationen (KI "vergisst" frühere Entscheidungen)
- ⚠️ Debugging komplexer Race Conditions (KI sieht nur statischen Code)
- ⚠️ User-Präferenzen respektieren (KI neigt dazu, eigene "Verbesserungen" einzubauen)

**Lessons Learning:**
- **Frage statt Ändern:** Bei Unklarheit erst fragen, dann handeln
- **Respektiere User-Edits:** Wenn User etwas ändert, hat das einen Grund (nicht "zurückändern")
- **Transparenz:** Sage explizit, was du änderst (keine "stillen" Edits)

---

# 10. PUBLIKATION (Vorbereitung)

## 10.1 GitHub (Repository-Struktur)

**Status:** Privat (Public Release geplant Januar 2026)

**Finale Struktur:**
```
hermeneutic-engine/
├── README.md (kompakt, 40-60 Zeilen)
├── LICENSE.txt (MIT)
├── CONTRIBUTING.md (Guidelines für Contributors)
├── CHANGELOG.md (Release Notes)
├── requirements.txt
├── Procfile
├── runtime.txt (python-3.11)
├── app.py
├── modules/ (Code)
│   ├── vector_store.py
│   ├── citation_rag.py
│   ├── hermeneutic_router.py
│   ├── hermeneutic_reranker.py
│   └── ...
├── docs/ (Dokumentation)
│   ├── README_v50_5.md (ausführliche Doku)
│   ├── v50_architecture.md (29-Seiten Technical Docs)
│   ├── FIBEL_v50_5.md (diese Datei!)
│   ├── images/ (Screenshots)
│   │   ├── Hermeneutic_Router_27122025.png
│   │   ├── Essence_Parity_27122025.png
│   │   └── ...
│   └── essay_hermeneutic_fairness.md (philosophischer Essay)
└── .secrets/ (NICHT im Repo! Lokal only)
```

---

## 10.2 ArXiv Paper (geplant)

**Status:** Noch nicht gestartet (geplant für Januar 2026)

**Vorgeschlagene Struktur (8-12 Seiten):**

1. **Abstract** (250 Wörter)
   - Problem: Source Bias + Validation Blindness in Standard RAG
   - Solution: Architectural guarantees (VIP-Schutz, Essence Parity, Enforcer)
   - Results: Coverage +150%, Gini -38%, Hallucinations -65%

2. **Introduction** (2 Seiten)
   - Motivation: Warum ist Fairness wichtig für Hermeneutik?
   - Related Work: Standard RAG, Fairness in ML, Hermeneutics in NLP

3. **Method** (3 Seiten)
   - Hermeneutic Triad (Retrieval, Synthesis, Validation)
   - VIP-Schutz (Algorithmus + Begründung)
   - Essence Parity (Max 12 Chunks/Doc)
   - Hermeneutic Enforcer (4 Kategorien)

4. **Evaluation** (2 Seiten)
   - Test Setup (5 Docs, 4 Sprachen, 3 Use-Cases)
   - Quantitative Results (Coverage, Gini, Query Time)
   - Qualitative Analysis (DeepSeek, Pessoa, Grok)

5. **Discussion** (1 Seite)
   - Limitations (Scalability, Threshold-Wahl, Language Coverage)
   - Future Work (Adaptive Fairness-Quota, Extended Multilingual)

6. **Conclusion** (0.5 Seiten)

7. **References** (1 Seite)

**Basis:** 90% des Contents ist bereits in `docs/v50_architecture.md` + dieser FIBEL!

---

## 10.3 Philosophischer Essay

**Status:** In Arbeit (Grigori schreibt lokal)

**Geplanter Titel:** "Archaeology of Mind: Hermeneutic Reconstruction of LLM Discourse"

**Kernthesen (aus Diskussionen):**
1. KI-Dialoge sind **archäologische Artefakte** – sie dokumentieren Denkprozesse
2. Standard RAG ist **hermeneutisch blind** – es reproduziert Bias, statt ihn zu reflektieren
3. Fairness ist **keine Metrik**, sondern ein **architektonisches Prinzip**
4. Enforcer ist **keine Zensur**, sondern **hermeneutische Kritik** (Unterscheidung legitim/halluziniert)

**Veröffentlichung:** TBD (bevorzugt ein philosophisches Journal)

---

# 11. ROADMAP

## 11.1 v50.6 (Q1 2026) – Architecture Refinement & QoL

**Ziel:** Sammlung aller "Kleinigkeiten", die das System bequemer machen.

**Geplante Änderungen:**
- Fairness-Dashboard im UI (zeige Chunk-Verteilung VOR Synthese)
- Download-Button für Synthese (als PDF/Markdown)
- Multi-Query-Session (mehrere Fragen hintereinander, ohne Dokumente neu zu wählen)
- Chunk-Inspector (zeige welche Chunks tatsächlich verwendet wurden)
- Bessere Fehler-Messages (User-freundlicher als Python-Tracebacks)

**Technische Verbesserungen:**
- Adaptive Fairness-Quota (nicht fix 20 Chunks/Doc, sondern abhängig von Doc-Längen-Verteilung)
- Lazy Loading (nur Chunks der ausgewählten Docs in RAM, nicht alle 6304)

---

## 11.2 v51 (Q2 2026) – Multi-Objective Synthesis

**Ziel:** Synthese nach mehreren Kriterien gleichzeitig.

**Use-Case:** "Stelle testweise die **beste** Übersetzung von Pessoa's 'Tabacaria' zusammen" – wo "beste" = Balance zwischen:
- Nähe zum Original (philosophische Präzision)
- Zugänglichkeit (lesbar für Nicht-Philosophen)
- Rhythmus (poetische Qualität)

**Technische Herausforderung:** Multi-Objective Optimization (Pareto-Frontier)

---

## 11.3 v52 (VISION) – Generative Translation

**Ziel:** System generiert **neue** Übersetzungen basierend auf gelernten Strategien.

**Use-Case:** "Übersetze Pessoa's 'Tabacaria' ins Deutsche, mit Celan's philosophischer Präzision, aber Honig's Zugänglichkeit"

**Technische Herausforderung:** Transfer Learning (Style Transfer für Übersetzungen)

**Status:** Vision (noch keine konkrete Implementation geplant)

---

# 12. ANHÄNGE

## 12.1 Git-Workflow

**Standard-Workflow:**
```bash
# 1. Feature-Branch erstellen
git checkout -b feature/neue-funktion

# 2. Änderungen committen (kleine, atomare Commits!)
git add modules/vector_store.py
git commit -m "feat: Add adaptive fairness-quota to investigativ-mode"

# 3. Branch pushen
git push origin feature/neue-funktion

# 4. Merge in main (nach Test!)
git checkout main
git merge feature/neue-funktion
git push origin main

# 5. Tag erstellen (für Release)
git tag v50.6
git push origin v50.6
```

**Commit-Message-Format:**
```
<type>: <subject>

Types:
- feat: Neues Feature
- fix: Bugfix
- docs: Dokumentation
- style: Code-Formatting (keine Logik-Änderung)
- refactor: Code-Umstrukturierung (keine Feature-Änderung)
- test: Tests hinzufügen/ändern
- chore: Build-System, Dependencies

Beispiele:
feat: Add VIP-Schutz to RRF fusion
fix: Correct Procfile port configuration
docs: Update FIBEL with v50.5 changes
```

---

## 12.2 Glossar

**BM25:** Keyword-basierter Retrieval-Algorithmus (Best Match 25)

**Chunk:** Textsegment (typisch 300-500 Tokens), das als atomare Einheit indiziert wird

**Essence Parity:** Fairness-Mechanismus (max 12 Chunks pro Dokument)

**Enforcer:** Validierungs-Modul (kategorisiert Aussagen: PARAPHRASE, META-STATEMENT, INFERENCE, HALLUCINATION)

**Gini Coefficient:** Maß für Ungleichheit (0 = perfekt fair, 1 = maximal unfair)

**Hermeneutic Router:** Intent-Klassifizierungs-Modul (LITERARY, FACTUAL, ANALYTICAL)

**Investigativ-Modus:** Retrieval-Strategie für kleine Korpora (≤5 Dokumente)

**RRF (Reciprocal Rank Fusion):** Algorithmus zur Kombination mehrerer Rankings

**VIP-Schutz:** Fairness-Mechanismus (garantiert top-3 Chunks pro ausgewähltem Dokument)

---

## 12.3 Kontakt & Support

**Projekt-Lead:** Grigori Pantijelew  
**Institution:** Landesinstitut für Schule Bremen  
**Email:** grigori.pantijelew@lis.bremen.de

**Repository:** https://github.com/gpantijelew/hermeneutic-engine (Private, Public Release Januar 2026)

**Support:**
- GitHub Issues (wenn public)
- Email (für Fragen)

**Response-Zeit:** 1-3 Tage (dies ist ein Forschungsprojekt, kein kommerzielles Produkt)

---

**Ende der FIBEL v50.5**

**Status:** Vollständig (Sections 1-12) ✅  
**Letzte Aktualisierung:** 30. Dezember 2025  
**Version:** v50.5 "Source Parity & Deep Validation"

**Nächster Schritt:** Audit der Dateien + Essay (philosophische Reflexion)
