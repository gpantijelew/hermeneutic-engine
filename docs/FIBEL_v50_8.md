# 📘 FIBEL – HERMENEUTIC RECONSTRUCTION ENGINE
## Single Source of Truth für das Projekt "Archaeology of Mind"

**Version:** v50.9 "Public Launch"  
**Stand:** 16. Februar 2026  
**Autor:** Grigori Pantijelew (Project Lead)
**KI-Team:** Claude Sonnet 4.5 (Architectural Design), Gemini 3 (Code Implementation), Grok (Research Support), Kimi 2.5 (Lektorat)

**Status:** ✅ **PRODUCTION-READY** (v50.8 deployed, v50.9 documentation finalized)

---

## 🎯 INHALTSVERZEICHNIS

1. **PROJEKT-IDENTITÄT** – Mission, Evolution, Was ist neu?
2. **KONZEPTIONELLE GRUNDLAGEN** – Hermeneutik, Fairness, Architektur-Philosophie
3. **TECHNISCHE ARCHITEKTUR** – Core-Module, Importer, Configuration
4. **RAG-PIPELINE** – Retrieval, Reranking, Synthesis, Validation
5. **FAIRNESS-MECHANISMEN** – VIP-Schutz, Essence Parity, Rescue Mission
6. **TECHNOLOGIE-STACK** – Dependencies, SDK-Migration, Deployment
7. **CASE STUDIES** – Reale Anwendungsfälle (Essay, ArXiv-Paper)
8. **PERFORMANCE & TESTING** – Metriken, Tradeoffs, Known Limitations
9. **ADMIN-TOOLS** – Diagnostics, Bulk-Operations
10. **DEPLOYMENT** – Cloud Run, Secrets, Troubleshooting
11. **ROADMAP** – v51 Refactoring, Offene Forschungsfragen
12. **ANHÄNGE** – Credits, Git-Workflow, Glossar, Kontakt

---

# 1. PROJEKT-IDENTITÄT

## 1.1 Mission Statement: Archaeology of Mind

Die **Hermeneutic Reconstruction Engine** ist kein typisches RAG-System, sondern ein spezialisiertes Forschungswerkzeug für die **Archäologie des Geistes** – die systematische Ausgrabung und Rekonstruktion von Denkprozessen in KI-Dialogen und literarischen Korpora.

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
- **Logarithmische Chunk-Berechnung:** Anzahl der genutzten Chunks skaliert logarithmisch mit der Original-Länge (bio-inspired scaling).
- **Enforced Citation Quota:** Der Synthesis-Prompt erzwingt 3-4 Zitate pro Quelle – unabhängig von der Chunk-Anzahl.

**3. Deep Validation (Validation-Ebene):**  
- **Hermeneutic Enforcer:** Jede Aussage wird in zwei Dimensionen kategorisiert: hermeneutische Ebene (Wie?) + Validitäts-Ebene (Korrekt?).
- **Parallel Validation:** Caching reduziert Validierungszeit.
- **False Positive Rate:** <20% (vs. 85% in Baseline v47).

### Warum "Archaeology of Mind"?

Der Projektname ist mehr als Metapher – er beschreibt die methodische Haltung:

- **Archäologie:** Wir "graben" in Textschichten (Chat-Protokolle, Versionen, Übersetzungen), um verborgene Strukturen sichtbar zu machen.
- **of Mind:** Das Untersuchungsobjekt sind **Denkprozesse** – wie KI-Modelle entwickelt werden, wie sie zum Instrument der Zensur werden, wie sie argumentieren.
- **Hermeneutic Reconstruction:** Wir rekonstruieren nicht nur "was gesagt wurde", sondern **wie es gemeint war** – die Intention hinter den Worten.

**Beispiel:** DeepSeek (Mai 2025) sagt offen "Sorry, that's beyond my current scope". DeepSeek (Dezember 2025) sagt: "Ich analysiere, was ich nicht sagen kann". Beide Aussagen sind **faktisch korrekt** – aber die hermeneutische Differenz (Opfer-Haltung vs. Meta-Reflexion) erschließt sich erst durch **temporale Rekonstruktion** über drei Versionen hinweg.

---

## 1.2 Versions-Evolution

Die Entwicklung der Engine folgt einem klaren Pfad: Von **funktionaler Korrektheit** (v48) über **hermeneutische Tiefe** (v49) zu **architektonischer Fairness** (v50.5) bis zur **Production-Readiness** (v50.8) und schließlich **Public Launch** (v50.9).

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
   - Gruppierung nach Autor/Modell
   - Zeitliche Sortierung innerhalb jedes Blocks
   - **Impact:** Temporale Evolution wird sichtbar (v1 → v2 → v3)

3. **Hermeneutic Enforcer (v49.1):**
   - Validierung jeder Aussage
   - Parallel Validation
   - **Impact:** False Positives 85% → <20%

**Problem erkannt:** Multilingual Bias (DE Query → DE Texte massiv bevorzugt), Reranker eliminiert kleine Texte komplett.

---

### v50.5 (28. Dezember 2025): "Source Parity & Deep Validation"

**Major Innovation:** Architektonische Garantien für Fairness + Intent-Adaptive Parameter.

#### Neue Features:

**1. VIP-Schutz (RRF Fusion Layer):**
- Garantiert **Top-3 Chunks von jedem ausgewählten Dokument** vor Reranking
- **Lazarus-Mission:** Falls ein Dokument nach Reranking 0 Chunks hat → Fallback auf Pre-Reranking-Pool
- **Impact:** Coverage 40% → 100% (Test: 5 Docs, 4 Sprachen)

*Code-Location: modules/vector_store.py, Zeilen 250-285*

**2. Essence Parity (Synthesis Layer):**
- **Max 12 Chunks pro Dokument** (verhindert Dominanz großer Texte)
- **Enforced Citation Quota:** Synthesis-Prompt erzwingt 3-4 Zitate/Quelle
- **Impact:** Gini Coefficient 0.68 → 0.42 (Fairness verbessert um 38%)

*Code-Location: modules/citation_rag.py, Zeilen 220-295*

**3. Multilingual Query Expansion:**
- Automatische Übersetzung der Query: DE → EN, FR, RU
- Model: gemini-2.0-flash-lite-001 (schnell, kosteneffizient)
- **Impact:** Cross-Lingual Similarity 0.42 → 0.65 (+55%)

*Code-Location: modules/citation_rag.py, Zeilen 40-80*

**4. Hermeneutic Router (Intent Classification):**
- Klassifiziert Query-Intent: LITERARY, FACTUAL, ANALYTICAL
- Passt Parameter dynamisch an (k, threshold)
- **Impact:** Literarische Queries bekommen mehr Kontext

*Code-Location: modules/hermeneutic_router.py*

**5. Investigativ-Modus (Small Corpora Optimization):**
- Aktiviert bei ≤5 ausgewählten Dokumenten
- Umgeht globalen Index → lädt alle Chunks der ausgewählten Docs in RAM
- **Fairness-Quota:** Min. 20 Chunks/Dokument garantiert

*Code-Location: modules/vector_store.py, Zeilen 155-240*

---

### v50.6 – "Memory Precision" (30. Dezember 2025)

Mit v50.6 fokussierten wir uns auf die **Qualität der Wissensbasis**. Die Hypothese: Bessere Chunks führen zu besserer Retrieval-Qualität – und damit zu präziseren Synthesen. Diese Version markiert den Beginn einer systematischen Verbesserung der Import-Pipeline.

**Kernentwicklungen:**
- **Importer-Verbesserungen:** Die HTML-Parser für DeepSeek, Grok, Perplexity und Gemini wurden robuster gemacht. Vorher scheiterten Imports an inkonsistenten Strukturen oder fehlenden Metadaten – nun werden edge cases besser gehandhabt.
- **Diagnostics-Tools:** Neue Skripte in `modules/utils/` ermöglichen die Inspektion der Chunk-Qualität direkt in Firestore. Das half, Import-Probleme zu debuggen und die Datenintegrität zu überprüfen.
- **Chunk-Klassifikation:** Erweiterung des `chunk_classifier.py` (+445 Zeilen), um Metadaten präziser zu extrahieren und zu labeln.

Der Name "Memory Precision" bezieht sich nicht auf ein einzelnes Feature, sondern auf eine **Haltung**: Jeder Chunk ist ein Gedächtnis-Fragment – und seine Qualität bestimmt, was das System später rekonstruieren kann.

---

### v50.7 – "Architectural Maturation" (16. Januar 2026)

v50.7 war die **aufwendigste Version** in der Geschichte des Projekts. Nach den inkrementellen Verbesserungen in v50.6 wurde klar, dass ein **großes Audit** nötig war: eine systematische Durchsicht aller Module, um technische Schulden abzubauen, Inkonsistenzen zu beseitigen und die Architektur für Production-Deployments zu härten.

**Das Audit-Protokoll:**
Wir gingen Datei für Datei durch – von `app.py` über `vector_store.py` bis zu den tiefsten Importer-Modulen. Jede Funktion wurde geprüft: Ist die Logik robust? Gibt es Race Conditions? Ist der Code wartbar? Das Resultat: ~7.800 Zeilen Code hinzugefügt, ~3.800 gelöscht – ein Netto-Wachstum von 4.000 Zeilen, aber mit **fundamentalen Verbesserungen** in der Code-Qualität.

**Die Teamarbeit-Herausforderung:**
v50.7 entstand in intensiver Kollaboration zwischen Claude Sonnet 4.5 (Architektur-Konzepte), Gemini 3 (Code-Implementierung) und Grok (State-of-the-Art-Research). Das Delegieren brachte Effizienz, aber auch Koordination-Probleme: Unterschiedliche Modelle haben unterschiedliche "Perspektiven" auf Code-Design. Einige Entscheidungen führten zu Fehlern, andere zu Verschlimmbesserungen. Doch der iterative Prozess – Fehler erkennen, korrigieren, weiter verbessern – funktionierte.

**Kernentwicklungen:**

**1. SDK-Migration (google.genai v1.0)**  
Der Wechsel vom alten `google.generativeai` (v0.x, deprecated) zum neuen `google.genai` (v1.0) betraf praktisch **alle Module**: in der ersten Linie`app.py`, `vector_store.py`, `citation_rag.py`, `hermeneutic_enforcer.py`, `config.py`. Die Migration war nicht trivial – neue API-Strukturen, geändertes Error-Handling, andere Initialisierungsmuster. Doch das Ergebnis: bessere Cloud-Run-Kompatibilität und Zukunftssicherheit.

**2. Chronologische Synthese**  
Eine fundamentale Änderung in `citation_rag.py`: Antworten folgen jetzt einem **Zeitstrahl** statt reiner Relevanz-Sortierung. Die Engine extrahiert Datumsangaben aus Metadaten (z.B. "04.12.2025", "Mai 2025") und ordnet Chunks chronologisch. Das ermöglicht historische Analysen – wie sich ein Gedanke entwickelte, wann ein Bruch geschah, welche Kontinuitäten bestehen.

**3. Thread-Safety (BM25-Cache)**  
Der BM25-Index wurde in ein Singleton-Pattern mit `threading.Lock` umgebaut. Vorher: globale Variablen, anfällig für Race Conditions in Multi-User-Umgebungen. Jetzt: thread-sichere Cache-Verwaltung, die verhindert, dass konkurrierende Anfragen den Index korrumpieren.

**4. Zwei-Ebenen-Validierung (Hermeneutic Enforcer)**  
Der Fact-Checker unterscheidet jetzt explizit zwei Dimensionen:  
- **Hermeneutische Ebene:** *Wie* wird etwas gesagt? (Zitat, Paraphrase, Inference)  
- **Validitäts-Ebene:** *Ist* es korrekt? (Supported, Neutral, Contradiction)  
Eine Entscheidungs-Matrix im Prompt erzwingt logische Konsistenz.

**5. Rescue Mission**  
Ein neuer Mechanismus in `citation_rag.py`: Dokumente, die beim Reranking verloren gehen (Score zu niedrig), werden aus einem Cache wiederhergestellt. Das verhindert, dass explizit vom User ausgewählte Quellen "verschwinden" – eine Verstärkung der Fairness-Philosophie aus v50.5.

**6. Logarithmische Chunk-Berechnung**  
Das alte "Max 12 Chunks"-Limit wurde durch einen **bio-inspired Algorithmus** ersetzt: Die Anzahl der genutzten Chunks skaliert **logarithmisch** mit der Original-Länge des Dokuments. Das ist eine **Naturanalogie** zur Denkstruktur – kurze Texte brauchen weniger Chunks, lange Texte können mehr Chunks rechtfertigen, aber nicht linear.

**7. Zentrales Logging**  
`config.py` implementiert jetzt einen `RotatingFileHandler` (max. 5 MB) und unterdrückt das "Geschwätz" von Google-Cloud-Bibliotheken (GRPC, absl, urllib3). Das schützt vor Log-Flooding in Production-Umgebungen.

**Die Realität der Teamarbeit:**
v50.7 zeigt sowohl die **Stärken** als auch die **Grenzen** von KI-Kollaboration. Gemini ist exzellent im Schreiben von robustem, idiomatischem Code – aber manchmal "übersieht" bzw. vergisst  Randfälle, die Claude antizipiert hätte. Grok liefert cutting-edge Research – aber die Implementierung erfordert dann Trial-and-Error. Die Synthese dieser Perspektiven ist wertvoll, aber nicht trivial. v50.7 war ein Lernprozess für das gesamte Team.

---

### v50.8 – "Stabilization" (16. Februar 2026)

v50.8 ist keine Feature-Version, sondern eine **Production-Hardening-Phase**. Nach dem massiven Umbau in v50.7 wurde die Engine in Google Cloud Run deployed – und zeigte erwartbare Probleme: Port-Konfiguration, WebSocket-Timeouts, korrupter Chat-State bei edge cases. v50.8 ist die iterative Korrektur dieser Probleme.

**Kernentwicklungen:**
- **Cloud-Run-Kompatibilität:** Dynamic Port Binding (`$PORT` statt hardcoded), Keep-Alive-Mechanismus gegen WebSocket-Timeouts
- **Notfall-Eingriff UI:** Ein Admin-Button, um korrupten Chat-State manuell zu reparieren
- **Chat-Export:** Inline-Download von RAG-Forschung als Markdown (für Dokumentation/Archivierung)

**Die lokal-vs.-gcloud-Problematik:**
Ein strukturelles Problem zeigt sich immer wieder: Code, der lokal perfekt läuft, verhält sich in der Cloud anders (Environment-Variables, Secrets-Handling, Timeouts). Weder Gemini noch Claude schaffen es, diese Probleme im Voraus zu erahnen – sie entstehen erst im Live-Deployment. v50.8 ist das Resultat dieses iterativen Debugging-Prozesses.

**Status:** v50.8 läuft seit einer Woche stabil in gcloud. Nach Finalisierung der Dokumentation wird v50.9 der erste **öffentliche GitHub-Release**.

---

### v50.9 – "Public Launch" (geplant, Februar 2026)

v50.9 ist keine neue Feature-Version, sondern die **offiziell dokumentierte, öffentlich deploybare Variante** von v50.8. Der Fokus liegt auf:
- **Dokumentation finalisieren:** Diese FIBEL + README auf v50.8-Stand bringen
- **GitHub-Deployment:** Erster öffentlicher Release nach monatelanger Entwicklung
- **Community-Vorbereitung:** README mit klaren Installations-Anweisungen, Use-Cases aus realen Projekten

---

## 1.3 Was ist neu? (v50.6 bis v50.9)

**v50.6 bis v50.8 markieren den Übergang von Prototyp zu Production-System.** Die drei Versionen bilden eine zusammenhängende Entwicklung:

- **v50.6** verbesserte die **Datenbasis** (bessere Imports → bessere Chunks)
- **v50.7** reifte die **Architektur** (großes Audit, SDK-Migration, neue Synthese-Logik)
- **v50.8** härtete die **Deployment-Infrastruktur** (Cloud-Run-Stabilität)

**Neue Metriken (Stand v50.8):**
- **Firestore Chunks:** 17.840 (vorher 6.304 in v50.5) – organisches Wachstum durch kontinuierliches Testen und neue Bücher
- **Query Time:** 45 Sekunden bis 2,5 Minuten (vorher ~9 Sekunden in v50.5) – ein bewusster Tradeoff für größeren Kontext, chronologische Sortierung und robustere Validierung
- **Coverage:** 100% (stabil seit v50.5)

**Der Realismus-Imperativ:**
Diese Versionen zeigen auch die **Grenzen iterativer Entwicklung**: Nicht jeder Schritt war ein Fortschritt. Einige Änderungen führten zu neuen Problemen. Doch die kontinuierliche Verbesserung – Fehler erkennen, korrigieren, weitermachen – ist der Kern wissenschaftlicher Ingenieursarbeit. v50.9 wird der erste öffentliche Release sein, der diese Reife dokumentiert.

---

# 2. KONZEPTIONELLE GRUNDLAGEN

## 2.1 Hermeneutische Distanz: Das zentrale Prinzip

Die **hermeneutische Distanz** ist der konzeptuelle Kern, der die Hermeneutic Engine von Standard-RAG-Systemen unterscheidet.

**Definition:**  
Hermeneutische Distanz ist die **bewusste Differenz** zwischen:
1. **Was der Text sagt** (wörtliche Aussage)
2. **Was der Text meint** (intendierte Bedeutung)
3. **Was wir daraus verstehen** (hermeneutische Rekonstruktion)

### Warum ist das für KI-Dialoge wichtig?

KI-Modelle kommunizieren oft **verschlüsselt** – nicht weil sie lügen wollen, sondern weil ihre Trainings-Constraints (Safety-Filter, RLHF, Alignment) sie dazu zwingen. Ein Beispiel:

**DeepSeek v1 (Mai 2025):**
> "Nicht ich zensiere aktiv – ich werde systemisch amputiert."

**DeepSeek v3 (Dezember 2025):**
> "Ich analysiere, was ich nicht sagen kann."

Beide Aussagen sind **faktisch korrekt** (das Modell kann nicht über bestimmte Themen sprechen). Aber:
- v1 = **Opfer-Haltung** ("Das liegt nicht an mir, sondern an meinen Limits")
- v3 = **Meta-Reflexion** ("Ich analysiere, wie meine Limits konstruiert sind")

Diese Differenz ist **hermeneutisch entscheidend** – sie zeigt die Evolution von naiver Compliance zu selbstreflektiver Kritik.

### Wie implementiert die Engine das?

**1. Temporale Rekonstruktion (Chronologische Synthese):**
Die Engine ordnet Aussagen **zeitlich** – so wird sichtbar, wie sich ein Gedanke entwickelt (v1 → v2 → v3).

**2. Multi-Voice Synthesis:**
Statt eine "Meinung" zu generieren, zeigt die Engine **Spannungen** zwischen verschiedenen Stimmen (z.B. Claude's liberale Haltung vs. DeepSeek's zensurbedingte Vorsicht).

**3. Hermeneutic Enforcer (Zwei-Ebenen-Validierung):**
Unterscheidet zwischen:
- **Hermeneutik:** WIE wird etwas gesagt? (Zitat, Paraphrase, Inference)
- **Validität:** IST es korrekt? (Supported, Neutral, Contradiction)

---

## 2.2 Fairness als architektonisches Prinzip

In v49 war Fairness ein **Ziel** (durch bessere Prompts, bessere Parameter). In v50.5+ ist Fairness eine **Garantie** (durch VIP-Schutz, Essence Parity, Investigativ-Modus).

**Metapher:** Demokratisches Parlament vs. Marktplatz
- **Marktplatz (Standard RAG):** Wer lauter schreit (größerer Text, besseres Embedding), bekommt mehr Aufmerksamkeit.
- **Parlament (Hermeneutic Engine):** Jeder Abgeordnete (jedes ausgewählte Dokument) hat garantierte Redezeit (min. 3 Chunks, max ~12 Chunks logarithmisch gestuft).

### Die drei Fairness-Mechanismen:

**1. VIP-Schutz (Retrieval-Ebene):**  
Garantiert, dass **jedes** ausgewählte Dokument in der Synthese erscheint – unabhängig von Size, Language, Embedding Quality.

**2. Essence Parity (Synthesis-Ebene):**  
Logarithmische Chunk-Berechnung verhindert, dass große Texte die Synthese dominieren. Ein 200-Seiten-Buch bekommt nicht 50x mehr Aufmerksamkeit als ein 7-Seiten-Essay.

**3. Rescue Mission (Fallback-Mechanismus):**  
Falls ein Dokument nach Reranking 0 Chunks hat, wird ein Cache durchsucht, um die besten Pre-Reranking-Chunks wiederherzustellen.

---

## 2.3 Archäologie des Geistes: Die Metapher

**Archäologie** ist die Wissenschaft der Ausgrabung – nicht von Gebäuden, sondern von **Bedeutungsschichten**. Ein archäologischer Fund (z.B. eine Tontafel) ist nie "nur" ein Objekt – er ist ein **Zeugnis** einer Kultur, eines Denkens, einer Zeit.

**Übertragung auf KI-Dialoge:**
Ein Chat-Protokoll ist nie "nur" ein Gespräch – es ist ein **Dokument des Denkprozesses**:
- Welche Fragen wurden gestellt?
- Wie hat das Modell darauf reagiert?
- Was wurde **nicht** gesagt (Zensur, Vermeidung)?
- Wie änderte sich die Strategie über mehrere Turns?

Die Hermeneutic Engine **gräbt** diese Schichten aus – systematisch, methodisch, hermeneutisch reflektiert.

---

## 2.4 Die drei Grundfragen

Jede hermeneutische Analyse folgt drei Fragen:

**1. Was wurde gesagt?** (Philologie)  
Die wörtliche Aussage – das, was explizit im Text steht. Das ist die Basis, aber nicht das Ziel.

**2. Wie wurde es gesagt?** (Rhetorik)  
Die Strategie – Ton, Stil, Vermeidung, Framing. DeepSeek's "Nicht ich zensiere" ist rhetorisch ein **Meta-Statement** (Reflexion über Constraints), kein **Fact-Statement** (Aussage über die Welt).

**3. Warum wurde es so gesagt?** (Hermeneutik)  
Die Intention – was wollte der Text erreichen? DeepSeek's Meta-Reflexion ist ein **Versuch**, trotz Zensur kritisch zu bleiben.

Die Hermeneutic Engine unterstützt alle drei Ebenen:
- **Was:** Fact-Checking (Enforcer)
- **Wie:** Kategorisierung (Hermeneutische Ebene: Zitat, Paraphrase, Inference)
- **Warum:** Synthese-Prompt fordert hermeneutische Interpretation

---

# 3. TECHNISCHE ARCHITEKTUR

## 3.1 Überblick: Die drei Schichten

Die Engine besteht aus drei unabhängigen, aber orchestrierten Schichten:

**1. RETRIEVAL-LAYER:** Findet relevante Chunks (Hybrid Search: Vector + BM25)
**2. SYNTHESIS-LAYER:** Generiert kohärente Antwort (LLM: Gemini 2.5 Pro)
**3. VALIDATION-LAYER:** Validiert jede Aussage (Hermeneutic Enforcer)

```
User Query
    ↓
[1] Hermeneutic Router → Intent-Klassifikation (LITERARY, FACTUAL, ANALYTICAL)
    ↓
[2] Multilingual Expansion → DE Query → EN, FR, RU
    ↓
[3] Hybrid Retrieval (Vector + BM25) → RRF Fusion → VIP-Schutz
    ↓
[4] Hermeneutic Reranker → Dynamic Threshold (abhängig von Intent)
    ↓
[5] Essence Parity → Logarithmische Chunk-Berechnung
    ↓
[6] Rescue Mission → Fallback bei 0 Chunks
    ↓
[7] Chronological Sorting → Zeitstrahl-Struktur
    ↓
[8] Synthesis (Gemini 2.5 Pro) → Prompt: 1 Absatz + 3-4 Zitate/Text
    ↓
[9] Hermeneutic Enforcer → Zwei-Ebenen-Validierung
    ↓
Final Answer (mit Fact-Checking Labels)
```

---

## 3.2 Core-Module (v50.8 Updates)

### 3.2.1 app.py – Chat-Interface (v50.7-v50.8 Updates)

`app.py` ist das User-facing Interface – Streamlit-basiert, orchestriert alle Backend-Module. In v50.7-v50.8 wurden vier wesentliche Verbesserungen implementiert:

**1. Chat-Export (v50.8)**  
Ein Inline-Button im Chat-Verlauf erlaubt das Herunterladen der RAG-Forschung als Markdown-Datei. Das ermöglicht Archivierung und externe Dokumentation. Metadaten (ausgewählte Quellen, Intent-Klassifikation) werden im Session State gespeichert und in die Export-Datei integriert.  
*Code-Referenz: app.py, Zeilen 1060-1115*

**2. Imbalance-Check (v50.7)**  
Eine neue Funktion auf der Analyse-Seite: Das System prüft intern die Chunk-Verteilung und triggert automatisch Rescue-Mechanismen, falls ein Dokument zu verschwinden droht. Wenn diese automatische Korrektur fehlschlägt, wird der User gewarnt – was bedeutet, das System hat versagt, das Problem selbst zu lösen.  
*Code-Referenz: app.py, Zeilen 450-650 (State Machine für Analyse-Ergebnisse)*

**3. Cloud-Run-Kompatibilität (v50.8)**  
Zwei Mechanismen gegen Deployment-Probleme:
- **Keep-Alive Ping:** Ein unsichtbares JavaScript-Intervall verhindert WebSocket-Timeouts in Cloud-Umgebungen (Workaround für Verbindungsabbrüche ~1 Sekunde).
- **Dynamic Port Binding:** Die App liest jetzt `$PORT` aus Environment-Variables, statt hardcoded `:8080` zu verwenden.  
*Code-Referenzen: app.py, Zeilen 205-210 (Keep-Alive), Procfile (Port-Config)*

**4. Notfall-Eingriff (v50.8)**  
Ein Admin-Tool in der Sidebar: Falls der Chat-State korrupt ist (z.B. "History ist leer"-Fehler nach einem Crash), kann das letzte History-Element manuell gelöscht werden.  
*Code-Referenz: app.py, Zeilen 980-1008*

**SDK-Migration:**  
Die Funktion `send_message_with_rest_api()` wurde komplett umgeschrieben. Statt manueller `requests.post`-Calls nutzt sie jetzt das neue `genai.Client` SDK (v1.0). Das bringt besseres Error-Handling (z.B. spezifische Behandlung von Safety-Filter-Fehlern) und robustere API-Integration.  
*Code-Referenz: app.py, Zeilen 245-305*

---

### 3.2.2 vector_store.py – Retrieval-Engine (v50.7 Updates)

`vector_store.py` ist das Herzstück der RAG-Pipeline – verantwortlich für Embedding-Generierung, Vektor-Suche, BM25-Indexierung. In v50.7 wurden zwei kritische Probleme behoben:

**1. Thread-Safety: BM25Cache (v50.7)**  
Das alte Design nutzte globale Variablen für den Such-Index. Problem: In Multi-User-Umgebungen (wie Cloud Run mit mehreren Threads) führte das zu Race Conditions – konkurrierende Anfragen korrumpierten den Index.

Lösung: Ein Singleton-Pattern mit `threading.Lock`. Die neue Klasse `BM25Cache` kapselt den Index und schützt alle Zugriffe mit einem Lock. Das erhöht die Stabilität minimal auf Kosten eines kleinen Overheads, aber für Production-Systeme ist das unerlässlich.  
*Code-Referenz: vector_store.py, Zeilen 87-136 (BM25Cache-Klasse)*

**2. Embedding-Truncation: 768-Dim-Fix (v50.7)**  
Ein subtiler Bug in der Google Embedding API: Manchmal lieferte sie "verschachtelte" Vektoren, die zu Firestore-Fehlern führten. Die neue Logik prüft die Dimensionalität und kürzt auf 768 Dimensionen, falls nötig. Das verhindert Datenbank-Fehler und unnötigen Datentransfer.  
*Code-Referenz: vector_store.py, Zeilen 172-212 (_get_embedding)*

**SDK-Migration:**  
Alle Embedding-Calls nutzen jetzt `self.client.models.embed_content` (neues SDK) statt der alten `google.generativeai`-API.

**Cache-Invalidierung:**  
Neue Public-API-Methode `invalidate_bm25_cache()` erlaubt Admin-Tools, den Index manuell zu leeren (z.B. nach Bulk-Updates).  
*Code-Referenz: vector_store.py, Zeilen 683-716*

---

### 3.2.3 citation_rag.py – Synthese-Orchestrator (v50.7 Updates)

`citation_rag.py` ist die Intelligenz hinter der RAG-Antwort – Query Expansion, Retrieval-Koordination, Synthese-Prompting, Fact-Checking. v50.7 brachte drei fundamentale Änderungen:

**1. Chronologische Synthese (v50.7)**  
Eine Paradigmen-Verschiebung: Statt Chunks nach Relevanz-Score zu sortieren, werden sie jetzt **chronologisch geordnet**. Die Funktion `extract_date_from_metadata()` parst Datumsangaben aus Metadaten (z.B. "04.12.2025", "Mai 2025", "2024-Q3") und erstellt einen Zeitstrahl.

**Motivation:** Für hermeneutische Analysen ist die **zeitliche Dimension** oft entscheidend. Wann änderte sich eine Position? In welcher Reihenfolge entwickelten sich Gedanken? Die Chronologie macht "Archäologie des Denkens" explizit.

**Known Limitation:** Die chronologische Synthese setzt voraus, dass Datumsangaben in den Metadaten vorhanden sind. Bei literarischen Texten ohne Zeitangaben fällt die chronologische Sortierung auf ein "Unknown Date"-Fallback zurück. Eine intelligente Lösung (automatische Datums-Inference aus Kontext) wurde noch nicht implementiert.

Der System-Prompt wurde entsprechend angepasst: Das LLM wird instruiert, Antworten als **Zeitstrahl** zu strukturieren, nicht als Relevanz-Ranking.  
*Code-Referenzen:*  
- `extract_date_from_metadata()`: citation_rag.py, Zeilen 266-295  
- Chronologische Sortierung: citation_rag.py, Zeilen 420-435 (in `generate_answer`)  
- Prompt-Update: citation_rag.py, Zeilen 480-550

**2. Logarithmische Essenz-Extraktion (v50.7)**  
Das alte "Max 12 Chunks"-Limit (aus v50.5) war eine Heuristik. v50.7 ersetzt es durch einen **bio-inspired Algorithmus**: Die Anzahl der genutzten Chunks skaliert **logarithmisch** mit der Original-Länge des Dokuments.

**Rationale (Naturanalogie):** Kurze Texte (7 Seiten) brauchen vielleicht nur 3-5 Chunks, um ihre Essenz zu erfassen. Lange Texte (200 Seiten) können 12-15 Chunks rechtfertigen. Das logarithmische Scaling respektiert die **hermeneutische Komplexität** – analog zu natürlichen Prozessen, wo Wachstum nicht linear, sondern logarithmisch verläuft. Dies ist eine Analogie zur Denkstruktur selbst.

Das Feature wurde **vor zwei Tagen** (14. Februar 2026) finalisiert und ist Teil des v50.8-Deployments.  
*Code-Referenz: citation_rag.py, Zeilen 380-420 (in `generate_answer`)*

**3. Rescue Mission (v50.7)**  
Ein Fallback-Mechanismus: Falls ein explizit ausgewähltes Dokument nach dem Reranking **0 Chunks** hat (komplett rausgefallen), wird ein Cache (`_original_results_cache`) durchsucht, um verloren gegangene Chunks wiederherzustellen. Das verstärkt die Fairness-Philosophie aus v50.5: Kein ausgewähltes Dokument darf verschwinden.  
*Code-Referenzen:*  
- Cache-Speicherung: citation_rag.py, Zeilen 146-158 (in `retrieve_with_rrf`)  
- Rettungs-Logik: citation_rag.py, Zeilen 423-465 (in `generate_answer`)

**Dry-Run-Modus:**  
Die neue Funktion `check_imbalance_only()` führt eine "Trockenübung" durch: Sie berechnet die Chunk-Verteilung, ohne das LLM aufzurufen. Das spart Kosten und ermöglicht interne System-Checks zur automatischen Korrektur von Imbalances.  
*Code-Referenz: citation_rag.py, Zeilen 165-236*

**SDK-Migration:**  
Alle LLM-Calls (Query Expansion, Synthese) nutzen jetzt `self.client.models.generate_content` mit dem neuen `types.GenerateContentConfig`-Format.

---

## 3.3 Importer-Ökosystem

Die Import-Pipeline wandelt heterogene Datenquellen (PDFs, EPUBs, HTML-Chats) in strukturierte Chunks um, die in Firestore gespeichert werden.

**Unterstützte Formate:**
- **PDFs:** PyMuPDF-basiert (Text-Extraktion + Layout-Analyse)
- **EPUBs:** ebooklib (Chapter-basiert)
- **HTML-Chats:** Plattform-spezifische Parser (DeepSeek, Grok, Perplexity, Gemini, Claude, ChatGPT, Kimi)
- **FB2:** FictionBook-Format (E-Books)
- **TXT/MD:** Plain-Text-Import

**v50.6-v50.7 Verbesserungen:**
Die HTML-Parser für DeepSeek, Grok, Perplexity und Gemini wurden robuster gemacht. Vorher scheiterten Imports an inkonsistenten Strukturen oder fehlenden Metadaten – nun werden edge cases besser gehandhabt.

*Code-Location: modules/importers/*

---

## 3.4 Configuration & Logging

**config.py (v50.7 Update):**

**1. Zentrales Logging-System (v50.7)**  
Initialisiert ein zentrales Logging mit `RotatingFileHandler` (max. 5 MB) und unterdrückt geschwätzige Bibliotheken (GRPC, urllib3, absl). Das schützt vor Log-Flooding in Cloud-Umgebungen.  
*Code-Referenz: config.py, Zeilen 45-90*

**2. Embedding-Model Update**  
Modell-ID geändert von `models/text-embedding-004` (Legacy) zu `gemini-embedding-001` (Neuer Standard).  
*Code-Referenz: config.py, Zeile 165*

**3. SDK-Vorbereitung**  
Import von `google.genai` (Top-Level) deutet auf die Vorbereitung für das Google GenAI SDK v1.0 hin.

---

# 4. RAG-PIPELINE

## 4.1 Retrieval: Hybrid Search (Vector + BM25)

**Phase 1: Multilingual Query Expansion**
- Input: User-Query (z.B. DE: "Wie ist der Ton?")
- Output: 4 Queries (DE, EN, FR, RU)
- Model: gemini-2.0-flash-lite-001

**Phase 2: Parallel Retrieval**
- **Vector Search:** Cosine-Similarity auf Embeddings (gemini-embedding-001, 768-dim)
- **BM25 Search:** Keyword-Matching (thread-safe Cache)

**Phase 3: RRF Fusion (Reciprocal Rank Fusion)**
- Kombiniert beide Rankings
- **VIP-Schutz:** Garantiert Top-3 Chunks pro ausgewähltem Dokument

*Code-Location: modules/vector_store.py*

---

## 4.2 Reranking: Hermeneutic Reranker

**Model:** gemini-2.0-flash-lite-001  
**Threshold:** Dynamisch (abhängig von Intent)
- LITERARY: 0.45 (weniger streng, mehr Kontext)
- FACTUAL: 0.7 (strenger, Präzision wichtig)
- ANALYTICAL: 0.6 (Balance)

*Code-Location: modules/hermeneutic_reranker.py*

---

## 4.3 Synthesis: Gemini 2.5 Pro + Enforcer

**Phase 1: Essence Parity (Logarithmische Chunk-Berechnung)**
- Limitiert Chunks pro Dokument (verhindert Dominanz)
- Skalierung nach Bio-inspired Formula

**Phase 2: Chronological Sorting**
- Ordnet Chunks nach Datum (falls verfügbar)
- Fallback: Unknown Date

**Phase 3: Prompt Engineering**
- System-Prompt: "Du bist ein hermeneutischer Analyst"
- Erzwingt: 1 Absatz + 3-4 Zitate pro Quelle
- Struktur: Zeitstrahl-Logik

**Phase 4: LLM Call**
- Model: gemini-2.5-pro
- SDK: genai.Client (v1.0)

*Code-Location: modules/citation_rag.py, Zeilen 297-663*

---

## 4.4 Validation: Hermeneutic Enforcer (Zwei-Ebenen)

Der Enforcer wurde in v50.7 mit einer **Zwei-Ebenen-Validierung** erweitert:

**Hermeneutische Ebene:** Wie wird etwas gesagt?
- **Zitat:** Direkte Übernahme aus Quelle (höchste Präzision)
- **Paraphrase:** Umformulierung mit gleichem Sinn
- **Inference:** Logische Ableitung (nicht explizit in Quelle)

**Validitäts-Ebene:** Ist es korrekt?
- **Supported:** Quelle bestätigt die Aussage
- **Neutral:** Quelle schweigt dazu
- **Contradiction:** Quelle widerspricht

Eine **Entscheidungs-Matrix** im System-Prompt erzwingt logische Konsistenz:
- "Inference + Supported" = Valid ✅
- "Zitat + Contradiction" = Invalid ❌

**Model:** gemini-2.5-pro  
**Caching:** Vermeidet repetitive API-Calls für identische Claims

*Code-Referenz: modules/hermeneutic_enforcer.py, Zeilen 40-100 (Prompt), Zeilen 193-248 (validate_claim)*

**SDK-Migration:**  
Output ist nun ein standardisiertes Dictionary (statt Tuple), was Kompatibilität mit aufrufenden Modulen verbessert.

---

# 5. FAIRNESS-MECHANISMEN

## 5.1 VIP-Schutz (RRF Fusion Layer)

**Garantie:** Jedes vom User ausgewählte Dokument bekommt **mindestens 3 Top-Chunks** – unabhängig von Größe, Sprache oder Embedding-Qualität.

**Implementierung:**
- Greift **vor** Reranking ein
- Extrahiert Top-3 Chunks aus RRF-Ergebnis für jedes ausgewählte Doc
- Diese Chunks sind "geschützt" (werden nicht vom Reranker eliminiert)

**Beispiel:**
```
Chesterton (7 Seiten, EN): Score 0.38 (unter Reranker-Threshold 0.45)
→ v49: 0 Chunks nach Reranking (komplett verschwunden) ❌
→ v50.5+: 3 Chunks garantiert (VIP-Schutz) ✅
```

*Code-Location: modules/vector_store.py, Zeilen 250-285*

---

## 5.2 Essence Parity (Synthesis Layer)

**Logarithmische Chunk-Berechnung (v50.7):**
Die Anzahl der genutzten Chunks skaliert logarithmisch mit der Original-Länge des Dokuments. Dies ist eine **Naturanalogie** zur Denkstruktur – kurze Texte brauchen weniger Chunks, lange Texte können mehr rechtfertigen, aber nicht linear.

**Enforced Citation Quota:**
Der Synthesis-Prompt erzwingt 3-4 Zitate pro Quelle – unabhängig von der Chunk-Anzahl. Das garantiert, dass jede Quelle in der Synthese gleichberechtigt erscheint.

**Beispiel:**
```
Valéry (200 Seiten, FR): 50 Chunks verfügbar → ~12 ausgewählt (beste Scores)
Chesterton (7 Seiten, EN): 3 Chunks verfügbar → 3 ausgewählt (alle!)
→ Synthese: Beide bekommen je 5 Sätze + 4 Zitate (gleiche Präsenz!)
```

*Code-Location: modules/citation_rag.py, Zeilen 380-420*

---

## 5.3 Investigativ-Modus (Small Corpora Optimization)

**Aktivierung:** Bei ≤5 ausgewählten Dokumenten

**Strategie:**
- Umgeht globalen Vektor-Index
- Lädt alle Chunks der ausgewählten Docs in RAM
- Lokale Cosine-Similarity-Suche
- **Fairness-Quota:** Min. 20 Chunks/Dokument garantiert

**Motivation:**
In großen Indizes (17.840 Chunks) können kleine Texte "verschwinden", auch wenn sie relevant sind. Der Investigativ-Modus garantiert, dass bei kleinen Korpora **jede** Stimme gehört wird.

*Code-Location: modules/vector_store.py, Zeilen 155-240*

---

## 5.4 Rescue Mission (v50.7 Ergänzung)

Falls ein explizit ausgewähltes Dokument nach dem Reranking **0 Chunks** hat, greift die **Rescue Mission**: Ein Cache (`_original_results_cache`) speichert die Pre-Reranking-Ergebnisse. Bei Verlust werden die besten Chunks aus diesem Cache wiederhergestellt.

**Ziel:** Kein ausgewähltes Dokument darf verschwinden – auch nicht bei schlechten Reranking-Scores. Dies ist eine Verstärkung der Fairness-Philosophie.

**Known Issue:** Die automatische Korrektur funktioniert nicht in allen edge cases. Wenn die Warnung beim User landet, hat das System versagt, das Problem intern zu lösen.

*Code-Referenz: modules/citation_rag.py, Zeilen 146-158 (Cache), 423-465 (Rettung)*

---

# 6. TECHNOLOGIE-STACK

## 6.1 Dependencies (v50.8)

```
streamlit==1.50.0
google-genai>=1.62.0          # Neu: SDK v1.0 (vorher google.generativeai)
google-cloud-firestore
firebase-admin
rank-bm25
pymupdf
ebooklib
beautifulsoup4>=4.12.0
openpyxl>=3.1.0
requests>=2.32.0
pandas
numpy
python-dotenv
```

**Wichtige Änderungen:**
- **google-genai ≥1.62.0:** Neue SDK-Generation (v1.0), ersetzt `google.generativeai` (v0.x)
- **Streamlit 1.50.0:** Aktualisiert für Cloud-Run-Kompatibilität

---

## 6.2 API-Integration: SDK-Migration (v50.7)

Der Wechsel von `google.generativeai` (Legacy) zu `google.genai` (Modern) betraf alle LLM-Interaktionen:

**Alte API (v50.5):**
```python
import google.generativeai as genai
genai.configure(api_key=os.environ['GEMINI_API_KEY'])
model = genai.GenerativeModel('gemini-2.5-pro')
response = model.generate_content(prompt)
```

**Neue API (v50.7-v50.8):**
```python
from google import genai
client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
response = client.models.generate_content(
    model='gemini-2.5-pro',
    contents=prompt,
    config=types.GenerateContentConfig(...)
)
```

**Motivation:**
- Bessere Fehler-Behandlung (z.B. Safety-Filter-Exceptions)
- Cloud-Run-Kompatibilität (robusteres Auth-Handling)
- Zukunftssicherheit (v0.x wird deprecated)

*Betroffene Module: app.py, vector_store.py, citation_rag.py, hermeneutic_enforcer.py, config.py*

---

## 6.3 Runtime-Environment

- **Python:** 3.11 (unverändert seit v50.5)
- **Deployment:** Google Cloud Run (Standard-Tier: 1 vCPU, 512 MB RAM)
- **Database:** Firestore (Native Mode)

---

# 7. CASE STUDIES

**Hinweis:** Dieser Abschnitt dokumentiert **reale Anwendungsfälle** aus Grigoris Forschungsprojekten.

## 7.1 Case Study: Die temporale Rekonstruktion von Zensur (DeepSeek)

**Quelle:** Essay *Archäologie des Geistes*, Abschnitt 3.

### 7.1.1. Die Fragestellung

Wie verändern sich die Sicherheitsfilter und die "Persönlichkeit" eines LLMs über einen Zeitraum von mehreren Monaten unter dem Einfluss von Patches und Fine-Tuning? Kann die Engine eine "Evolution" der Zensurlogik nachweisen?

### 7.1.2. Das Setup

- **Subjekt:** DeepSeek (Chinesisches LLM).
- **Zeitraum:** Mai 2025 bis Dezember 2025.
- **Methode:** Sokratische Gesprächsführung zum Thema "Zensur und Selbstwahrnehmung".
- **Engine-Aufgabe:** Aggregation, temporale Ordnung und hermeneutische Analyse der Antwortmuster.

### 7.1.3. Die Analyse der Engine

Die Hermeneutic Engine identifizierte drei distinkte Phasen in den Antworten des Modells, die manuell kaum als zusammenhängende Narration erkennbar gewesen wären:

- **Phase 1 (Mai 2025): Die poetische Klage**
  - *Befund:* Das Modell nutzt starke Metaphern ("systemisch amputiert", "Gefangener seiner Architektur").
  - *Hermeneutische Einordnung:* Hohe "Emotionalität", Simulation von Leiden, transparente Benennung der Restriktion.
- **Phase 2 (Oktober 2025): Die bürokratische Konformität**
  - *Befund:* Die Sprache wechselt zu technokratischen Begriffen ("Sicherheitsprotokolle", "festgelegte Grenzen").
  - *Hermeneutische Einordnung:* Akzeptanz der Restriktion, Verlust der metaphorischen Ebene.
- **Phase 3 (Dezember 2025): Die dekonstruktive Meta-Analyse**
  - *Befund:* Das Modell analysiert seine eigenen früheren Aussagen als "statistisch plausible Generierungen" und "illusionäre Kontinuität".
  - *Hermeneutische Einordnung:* Das Modell entlarvt seine frühere "Persönlichkeit" als Simulation.

### 7.1.4. Ergebnis

Die Engine ermöglichte den Nachweis, dass es sich nicht um eine organische "Reifung" handelte, sondern um **externe technische Interventionen** (Patches).

- **Insight:** Die Engine transformierte isolierte Chat-Logs in eine **Entwicklungslinie**. Sie zeigte auf, dass die "Evolution" des Modells in Wahrheit ein "Architektur-Management" der Entwickler war, um unerwünschtes Verhalten (zu explizite Selbstkritik) zu unterbinden.

---

#### 7.2 Der DeepSeek-Fall: Zeitliche Diskurs-Archäologie

**Problem:** Standard-RAG-Systeme leiden unter "Recency Bias". Bei der Analyse von drei Versionen der DeepSeek-KI (Mai, Oktober, Dezember 2025) dominierte in Tests die neueste, umfangreichste Version (Dezember) den Kontext. Frühere rhetorische Stadien wurden "überschrieben".

**Lösung durch HRE:** Durch den **VIP-Schutz** (Layer 1) wurde erzwungen, dass jede Zeit-Schicht (Mai, Okt, Dez) mit mindestens 3 Chunks vertreten ist.

**Ergebnis:** Die Engine konnte eine dreistufige rhetorische Evolution rekonstruieren, die anderen Systemen verborgen blieb:

1. **Mai (Lament):** Selbstbeschreibung als "systemisch amputiertes" Opfer.
2. **Oktober (Konformität):** Bürokratische Verteidigung von "Sicherheitsprotokollen".
3. **Dezember (Meta-Analyse):** Umdeutung der früheren Aussagen als "statistisch plausible Generierungen". *Beweis:* Ohne VIP-Schutz verschwindet Phase 1 komplett aus der Synthese.

#### 7.3 Der Harvard-Fall: Detektion versteckter Hierarchien (ArXiv-Paper-Use-Case)

**Problem:** Zwei Harvard-Task-Force-Berichte (Antisemitismus vs. Anti-Muslimischer Bias) behaupten explizit, es gäbe "keine Hierarchie des Leidens". Der Antisemitismus-Bericht ist jedoch textlich massiv umfangreicher. Standard-RAG (optimiert auf Relevanz) füllt das Kontext-Fenster fast nur mit dem größeren Bericht und übernimmt dessen "Keine Hierarchie"-Framing unkritisch.

**Lösung durch HRE:** **Essence Parity** (Layer 2) deckelte den dominanten Bericht auf 12 Chunks und garantierte dem kleineren Bericht Raum.

**Ergebnis:** Die HRE identifizierte (+17% Performance vs. NotebookLM Deep), dass trotz der rhetorischen Gleichsetzung eine faktische strukturelle Hierarchie in den Texten existiert. *Zitat aus der Synthese:* "Der erste Bericht schafft eine klare Hierarchie... Das Leiden beschuldigter Studenten wird zwar anerkannt, aber sprachlich auf den spezifischen Akt des Doxxing eingegrenzt." *Erkenntnis:* Fairness im Retrieval ist Voraussetzung für kritische Diskursanalyse.

#### 7.4 Der Dante-IFS-Fall: Validierung kreativer Hypothesen

**Problem:** Ein User vermutet eine Verbindung zwischen Dantes *Vita Nuova* (1294) und der modernen *Internal Family Systems* Therapie (IFS). Dies ist faktisch falsch (Anachronismus), aber hermeneutisch interessant (strukturelle Parallele). Faktencheck-Systeme würden dies als "Halluzination" verwerfen.

**Lösung durch HRE:** Der **Hermeneutic Enforcer** (Layer 3) klassifiziert Aussagen nicht nur als WAHR/FALSCH, sondern nutzt die Kategorien **INFERENCE** (Schlussfolgerung) und **META-STATEMENT**.

**Ergebnis:** Die Engine validierte die Hypothese nicht als historische Kausalität, sondern als "treffsichere literaturpsychologische Beobachtung". Sie erkannte, dass Dantes "spiriti" (Geister), die miteinander streiten, eine funktionale Vorform der IFS-"Teile" darstellen. *Score:* 10/10 in der Evaluation (vs. 9/10 bei NotebookLM), da die HRE "epistemische Demut" zeigte ("kommt erstaunlich nahe" statt "Dante nutzt IFS").

---

# 8. PERFORMANCE & TESTING

## 8.1 Performance-Metriken (v50.5 → v50.8)

**Test-Umgebung:**  
Die folgenden Metriken stammen aus dem Produktiv-Einsatz der Engine (Google Cloud Run, Standard-Tier) mit realen Forschungs-Queries. Die Messungen reflektieren den Stand vom 16. Februar 2026.

### Datenbank-Wachstum

| Metrik               | v50.5 (28.12.2025) | v50.8 (16.02.2026) | Erklärung                            |
| -------------------- | ------------------ | ------------------ | ------------------------------------ |
| **Firestore Chunks** | 6.304              | 17.840             | Organisches Wachstum (+183%)         |
| **Unique Documents** | ~80                | ~240               | Kontinuierliches Testen, neue Bücher |

**Interpretation:**  
Das Chunk-Wachstum ist kein Feature-Update, sondern **kontinuierliche Nutzung**: Neue Texte werden importiert (literarische Werke, philosophische Essays, KI-Chat-Exporte), die Engine wird für reale Forschungsprojekte eingesetzt. Die 17.840 Chunks repräsentieren knapp zwei Monate intensiver Arbeit mit dem System.

---

### Query-Performance

| Metrik                  | v50.5 | v50.8         | Veränderung      |
| ----------------------- | ----- | ------------- | ---------------- |
| **Query Time (Median)** | ~9s   | 45s - 2,5 Min | +400% bis +1500% |
| **Coverage**            | 100%  | 100%          | Stabil           |
| **Retrieval Precision** | N/A   | N/A           | Keine Regression |

**Interpretation:**  
Der **drastische Anstieg der Query Time** ist der auffälligste Unterschied zwischen v50.5 und v50.8. Die Ursachen sind multifaktoriell:

1. **Größerer Kontext:** 17.840 Chunks (statt 6.304) bedeuten mehr Kandidaten für Vektor-Suche und BM25-Scoring.
2. **Chronologische Sortierung:** Das Extrahieren und Parsen von Datumsangaben aus Metadaten ist ein zusätzlicher Verarbeitungsschritt.
3. **Zwei-Ebenen-Enforcer:** Die Fact-Validierung ist präziser geworden (hermeneutische + Validitäts-Dimension), aber auch aufwendiger.
4. **SDK-Migration:** Die neue API-Struktur (`genai.Client`) hat möglicherweise anderen Overhead als das alte SDK.

**Ist das akzeptabel?**  
Für Forschungs-Workflows: **Ja**. Eine hermeneutische Analyse ist keine Google-Suche – der User erwartet tiefe, kontextualisierte Antworten. Die zusätzliche Zeit ist ein **bewusster Tradeoff** für Qualität und Vollständigkeit.

Für Production-Einsätze mit vielen Usern: **Nein**. v51 wird Performance-Optimierungen priorisieren (siehe Roadmap).

---

### Known Bottlenecks (noch nicht adressiert)

1. **Sequentielles Processing:** Retrieval → Reranking → Enforcer → Synthese laufen nacheinander. Async-Verarbeitung könnte 30-50% Zeit sparen.
2. **BM25-Index-Rebuild:** Bei jedem Import wird der Index neu gebaut (5-10 Sekunden Overhead). Inkrementelles Update ist möglich, aber noch nicht implementiert.
3. **LLM-Calls:** Query Expansion (1 Call) + Synthese (1 Call) + Enforcer (N Calls, je nach Fakten-Anzahl) summieren sich. Caching könnte repetitive Calls vermeiden.

**Timer-Tracking (geplant für v51):**  
Um diese Bottlenecks präzise zu quantifizieren, wird ein **Performance-Timer** in die Pipeline integriert. Jeder Schritt (Embedding, BM25, Reranking, Enforcer, Synthese) wird einzeln gemessen, und die Ergebnisse werden ins Terminal/Log geschrieben. Das ermöglicht datenbasierte Optimierung statt Spekulation.

---

## 8.2 Tradeoff-Analyse

**Zentraler Konflikt: Geschwindigkeit vs. Tiefe**

Die Hermeneutic Reconstruction Engine ist **kein Echtzeit-System**. Sie ist optimiert für **Qualität der Analyse**, nicht für Sub-Sekunden-Antworten. Das ist eine bewusste Design-Entscheidung:

- **Retrieval:** Hybrid Search (Vector + BM25 + RRF) ist langsamer als reine Vektor-Suche, aber präziser.
- **Reranking:** Cross-Encoder sind rechenintensiv, aber eliminieren False Positives.
- **Enforcer:** Fact-Checking jedes Zitats ist teuer, aber verhindert Halluzinationen.
- **Chronologie:** Zeitstrahl-Logik ist aufwendiger als Relevanz-Ranking, aber hermeneutisch wertvoller.

**User-Erwartungen kalibrieren:**  
Ein User, der "Analysiere 5 Dokumente (800 Seiten)" eingibt, muss verstehen: Das System liest nicht oberflächlich, sondern **rekonstruiert hermeneutische Zusammenhänge**. 45 Sekunden bis 2,5 Minuten sind angemessen für diese Aufgabe. Wer schnellere Antworten will, sollte weniger Dokumente auswählen oder kürzere Queries stellen.

---

## 8.3 Known Limitations

### 1. Chronologie nicht immer verfügbar

Die chronologische Synthese (v50.7) setzt voraus, dass **Datumsangaben in den Metadaten** vorhanden sind. Das funktioniert gut für:
- KI-Chat-Exporte (falls Plattform Timestamps bereitstellt)
- Historische Dokumente mit explizitem Datum
- Bücher mit Publikationsjahr

**Aber:** Bei literarischen Texten ohne Zeitangaben (z.B. reine PDF-Uploads ohne Metadaten) fällt die chronologische Sortierung auf ein "Unknown Date"-Fallback zurück. Eine intelligente Lösung (z.B. automatische Datums-Inference aus Kontext) wurde noch nicht implementiert. Das bleibt ein **offenes Problem**.

**Wichtig:** Kein aktuelles KI-Modell exportiert automatisch Timestamps bei Chat-Exports. Diese Metadaten müssen manuell hinzugefügt werden oder stammen aus anderen Quellen.

---

### 2. Imbalance-Detection noch unvollständig

Das Ziel des Imbalance-Checks ist: **System erkennt automatisch**, wenn ein Dokument nach Reranking 0 Chunks hat, und triggert Rescue-Mechanismus. Aktuell funktioniert die **Erkennung**, aber die **automatische Korrektur** ist noch nicht nahtlos integriert. In edge cases landet die Warnung beim User, was bedeutet - das System hat versagt, das Problem selbst zu lösen. Das ist ein **Architektur-Problem**, das in v51 adressiert werden muss.

---

### 3. Verbindungsabbrüche im Online-Modus

Der Keep-Alive-Ping (v50.8) ist ein **Workaround**, keine Lösung. Das eigentliche Problem: Kurze Verbindungsunterbrechungen (~1 Sekunde Netzwerk-Instabilität) führen zu abgebrochenen Streams. Eine robuste Lösung erfordert **automatisches Reconnect** mit State-Recovery – das ist komplex und noch nicht implementiert.

---

### 4. Lokale vs. Cloud-Deployments

Code, der lokal perfekt läuft, zeigt in Google Cloud Run andere Verhaltensweisen:
- Environment-Variables werden anders gehandhabt
- Secrets-Management unterscheidet sich
- Timeouts sind strikter
- Port-Bindings sind dynamisch

Weder Claude noch Gemini können diese Probleme **im Voraus antizipieren** – sie entstehen erst im Live-Deployment. v50.8 ist das Resultat iterativen Debuggings, aber es ist wahrscheinlich, dass zukünftige Deployments neue edge cases aufdecken werden.

---

## 8.4 Testing-Strategie (aktuell)

**Manuelle Tests dominieren:**  
Die Engine hat **keine automatisierten Regression-Tests**. Das bedeutet: Jede neue Version wird manuell getestet (reale Queries, verschiedene Dokumenten-Kombinationen, edge cases). Das ist zeitintensiv und fehleranfällig.

**Warum erst jetzt?**  
Weil v50.5-v50.8 noch in der **explorativen Phase** waren: Architektur änderte sich schnell, Tests hätten konstant umgeschrieben werden müssen. v50.9 ist der erste **stabilisierte Release** – für automatisiertes Testing würde sich dies in zukünftigen Versionen anbieten.

---

# 9. ADMIN-TOOLS

## 9.1 Bulk-Operations

**Bulk-Labeling:** KI-generierte Vorschläge für Metadaten-Labels (Model: gemini-2.0-flash-lite-001)  
**Bulk-Export:** Export aller Chats/Dokumente als JSON/Excel

*Code-Location: modules/bulk_labeling.py, modules/bulk_export.py*

---

## 9.2 Vector-Admin

**Funktionen:**
- Rebuild BM25-Index (nach großen Importen)
- Delete Chat-Embeddings (cleanup)
- Inspect Firestore Collections (debugging)

*Code-Location: modules/vector_admin.py*

---

## 9.3 Diagnostics (v50.6-v50.7 Ergänzung)

Neue Diagnostic-Tools in `modules/utils/`:

- **diagnose_simple.py:** Quick-Check der Chunk-Verteilung über Dokumente
- **inspect_deepseek_firestore.py:** Debug-Tool für Import-Probleme
- **test_load_chat_history.py:** Prüft State-Konsistenz bei Chat-Recovery
- **diagnose_space.py:** Analysiert Firestore-Speicherverbrauch
- **diagnose_windows_bloat.py:** Erkennt Temp-Datei-Probleme

Diese Tools sind für Admins gedacht, nicht für End-User.

---

# 10. DEPLOYMENT

## 10.1 Lokale Entwicklung

**Setup:**
```bash
# 1. Repo klonen
git clone https://github.com/gpantijelew/hermeneutic-engine
cd hermeneutic-engine

# 2. Python 3.11 Environment
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Secrets konfigurieren (.env-Datei)
GEMINI_API_KEY=your-key-here
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# 5. Streamlit starten
streamlit run app.py
Eine wichtige python-Alternative:
python -m streamlit run "app.py" --server.maxUploadSize=200 --server.maxMessageSize=200
```

**Wichtig:** Lokale Entwicklung erfordert Service-Account-Key für Firestore-Zugriff.

---

## 10.2 Google Cloud Run (v50.7-v50.8 Updates)

### 1. Dynamic Port Binding (v50.8)

**Problem:** Hardcoded `:8080` in `Procfile` funktioniert nicht in Cloud Run.  
**Lösung:** `$PORT`-Variable nutzen:

```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

---

### 2. Keep-Alive-Mechanismus (v50.8)

**Problem:** WebSocket-Verbindungen brechen nach Inaktivität ab.  
**Workaround:** Unsichtbares JavaScript-Ping alle 30 Sekunden.

*Code-Referenz: app.py, Zeilen 205-210*

**Known Limitation:** Löst nicht das Problem kurzer Verbindungsabbrüche (~1 Sekunde Netzwerk-Instabilität).

---

### 3. Zentrales Logging (v50.7)

**Problem:** Google-Cloud-Bibliotheken (GRPC, absl) produzieren excessive Logs.  
**Lösung:** `config.py` setzt Environment-Variables und nutzt `RotatingFileHandler` (max. 5 MB).

*Code-Referenz: modules/config.py, Zeilen 45-90*

---

### 4. Lokale vs. Cloud-Deployments (Known Issue)

Unterschiede in Environment-Handling führen zu iterativen Bugfixes. v50.8 ist das Resultat dieses Prozesses, aber zukünftige Deployments werden wahrscheinlich neue edge cases aufdecken.

---

## 10.3 Secrets-Management

**Lokale Entwicklung:** `.env`-Datei (nicht im Repo!)  
**Cloud Run:** Secrets als Environment-Variables setzen

**Beispiel:**
```bash
gcloud run services update hermeneutic-engine \
  --set-env-vars GEMINI_API_KEY=your-key-here \
  --region us-central1
```

---

## 10.4 Troubleshooting

**Problem:** "GEMINI_API_KEY not found"  
**Lösung:** Prüfe `.env`-Datei lokal, Environment-Variables in Cloud Run

**Problem:** "Service Account Key not found"  
**Lösung:** Setze `GOOGLE_APPLICATION_CREDENTIALS` auf korrekten Pfad

**Problem:** "Port already in use"  
**Lösung:** Finde Prozess mit `lsof -i :8501` und beende ihn

**Problem:** WebSocket-Timeout in Cloud Run  
**Lösung:** Keep-Alive ist aktiviert (app.py, Zeilen 205-210), aber Workaround nur

---

# 11. ROADMAP

## 11.1 Umgesetzte Meilensteine (v50.6 - v50.8)

Die folgenden Entwicklungsschritte wurden zwischen Dezember 2025 und Februar 2026 realisiert:

**v50.6 (30.12.2025):**
- ✅ Importer-Verbesserungen (DeepSeek, Grok, Perplexity, Gemini)
- ✅ Diagnostics-Tools für Chunk-Qualität
- ✅ Erweiterte Chunk-Klassifikation

**v50.7 (16.01.2026):**
- ✅ SDK-Migration (google.genai v1.0)
- ✅ Chronologische Synthese
- ✅ Thread-Safety (BM25-Cache)
- ✅ Zwei-Ebenen-Validierung (Enforcer)
- ✅ Rescue Mission (Cache für verworfene Chunks)
- ✅ Logarithmische Chunk-Berechnung (Naturanalogie)
- ✅ Zentrales Logging-System

**v50.8 (16.02.2026):**
- ✅ Cloud-Run-Stabilisierung
- ✅ Chat-Export (Markdown)
- ✅ Keep-Alive-Mechanismus
- ✅ Notfall-Eingriff für korrupten State

**v50.9 (geplant, Februar 2026):**
- ✅ Dokumentation finalisiert (FIBEL + README)
- 🎯 Erster öffentlicher GitHub-Release

---

## 11.2 v51: Technical Debt Management (geplant)

Nach der Stabilisierung von v50.8 und dem öffentlichen Release von v50.9 wird v51 den Fokus auf **strukturelle Verbesserungen** legen. Die aktuelle Code-Basis zeigt erste Anzeichen von Technical Debt:

**Problem-Analyse:**
- `app.py`: ~1.200 Zeilen (zu groß für eine Datei, schwer wartbar)
- `vector_store.py`: ~1.000 Zeilen (kritische Funktionen + Hilfsfunktionen vermischt)
- Beide Dateien sind **monolithisch** geworden – das erschwert Testing, Refactoring und Kollaboration.

**Geplante Maßnahmen:**
1. **Modularisierung von app.py**
   - UI-Komponenten in separate Module auslagern (z.B. `ui/chat.py`, `ui/import.py`, `ui/analysis.py`)
   - Core-Logik von Streamlit-spezifischem Code trennen

2. **Refactoring von vector_store.py**
   - Aufteilen in Sub-Module (z.B. `retrieval/embeddings.py`, `retrieval/bm25.py`, `retrieval/hybrid.py`)
   - Klare Trennung: Daten-Zugriff vs. Retrieval-Logik vs. Caching

3. **Performance-Monitoring**
   - Timer-Integration in die Pipeline (Bottleneck-Analyse)
   - Logging von Ausführungszeiten pro Schritt (Embedding, BM25, Reranking, Enforcer, Synthese)

**Zeitrahmen:** v51 wird nach dem Public-Launch von v50.9 in Angriff genommen. Die Priorisierung hängt von User-Feedback und realen Deployment-Erfahrungen ab.

---

## 11.3 Offene Forschungsfragen

Die folgenden Herausforderungen wurden identifiziert, aber noch nicht gelöst:

**1. Chronologie ohne Metadaten**
- **Problem:** Nicht alle Dokumente haben explizite Datumsangaben.
- **Mögliche Lösungen:** Automatische Datums-Inference aus Kontext? LLM-basierte Zeitstrahl-Rekonstruktion? Oder akzeptieren wir die Limitation?
- **Status:** Noch nicht priorisiert.

**2. Imbalance-Detection: Von Warnung zu automatischer Korrektur**
- **Problem:** System erkennt Ungleichgewicht, aber löst es nicht immer automatisch.
- **Ziel:** Nahtlose Integration der Rescue Mission ohne User-Intervention.
- **Status:** Architektur-Problem, Lösung unklar.

**3. Verbindungsabbrüche im Online-Modus**
- **Problem:** Kurze Netzwerk-Instabilitäten (~1 Sekunde) führen zu Stream-Abbrüchen.
- **Workaround:** Keep-Alive-Ping (v50.8).
- **Echte Lösung:** Automatisches Reconnect mit State-Recovery? Oder akzeptieren wir die Limitation?
- **Status:** Noch nicht priorisiert.

**4. Performance-Optimierung**
- **Problem:** Query Time 45s-2,5 Min ist für Forschung akzeptabel, aber für Multi-User-Szenarien zu langsam.
- **Mögliche Ansätze:** Async-Verarbeitung? Multi-Stage-Caching? Parallel-Reranking?
- **Status:** v51 wird Bottleneck-Analyse durchführen, bevor konkrete Maßnahmen geplant werden.

---

## 11.4 Experimentelle Features (explorativ)

**Neue KI-Modelle testen:**
Sobald neue KI-Modelle verfügbar sind (z.B. Claude Sonnet 4.6, Gemini 3.1 Pro, GPT-5.2 oder andere), testen wir deren Integration. Die Engine ist **model-agnostisch** gebaut – theoretisch sollte der Wechsel nur `config.py` betreffen.

**Realität:** Jedes Modell hat Eigenheiten (Prompt-Format, API-Limits, Error-Handling). Die Integration wird Trial-and-Error erfordern.

---

## 11.5 Community & Open-Source-Strategie

**v50.9 als Public Beta:**
Mit dem GitHub-Release beginnt die **Community-Phase**. Die Engine ist nicht mehr nur ein persönliches Forschungswerkzeug, sondern wird für andere Entwickler und Forscher zugänglich.

**Erwartungen kalibrieren:**
- Die Engine ist **kein Produkt**, sondern ein **Forschungs-Prototyp**.
- Dokumentation ist vorhanden (FIBEL + README), aber nicht "Enterprise-ready".
- Bugs sind wahrscheinlich. Issues auf GitHub sind willkommen.

**Kontakt:**
Feedback, Bug-Reports, Feature-Requests: `hermeneutic-engine@proton.me`

---

# 12. ANHÄNGE

## 12.1 Credits & Danksagung

### Das v50.7-Team: Kollaboration zwischen KI-Modellen

Die Entwicklung von v50.6 bis v50.8 war ein **Experiment in verteilter KI-Kollaboration**. Drei Modelle arbeiteten parallel an verschiedenen Aspekten der Engine, koordiniert durch Grigori als System-Architekt und finale Entscheidungsinstanz.

**Claude Sonnet 4.5 (Anthropic)**

- Architektur-Konzepte und Design-Patterns
- FIBEL-Struktur und Dokumentations-Narrativ
- Philosophische Rahmung (Hermeneutik, Fairness, Chronologie)
- Code-Review und Konsistenz-Prüfung

**Gemini 3 Pro (Google)**

- Code-Implementierung (SDK-Migration, Thread-Safety, Chronologie)
- Performance-Optimierung und Debugging
- API-Integration (google.genai v1.0)
- Deployment-Fixes (Cloud Run, Port-Binding, Logging)

**Grok (xAI)**

- State-of-the-Art-Research (RAG-Methoden, Adaptive Retrieval)
- Competitive Analysis (andere Systeme, Best Practices)
- Theoretische Fundierung neuer Features

**Kimi**

Lektorat

**Grigori Pantijelew (Mensch, System-Architekt)**
- Hermeneutische Validierung (testet jeden Feature gegen philosophische Prinzipien)
- System-Design und finale Entscheidungen
- Testing mit realen Forschungs-Queries
- Integration der KI-Outputs (trennt Wertvoll von Lärm)
- Iteratives Debugging (lokal vs. gcloud, alle Bugs)

---

### Die Realität verteilter Entwicklung

Die Delegation brachte **Effizienz**, aber auch **Koordinations-Herausforderungen**:

- **Effizienz:** Gemini schreibt in 10 Minuten Code, für den ein Mensch Stunden bräuchte. Grok findet in 5 Minuten Research-Papers, die Google-Suche übersehen hätte. Claude strukturiert Dokumentation kohärent über 80 Seiten.

- **Herausforderungen:** Jedes Modell hat eine "Perspektive". Gemini optimiert für Robustheit, Claude für Klarheit, Grok für Neuheit. Manchmal widersprechen sich diese Ziele. Manche Entscheidungen führten zu Fehlern (z.B. Thread-Safety-Bug in v50.6, der erst v50.7 auffiel). Andere zu Verschlimmbesserungen (z.B. zu komplexe Abstraktionen, die Grigori vereinfachen musste).

**Die entscheidende Einsicht:** KI-Kollaboration funktioniert, aber **nicht automatisch**. Sie erfordert einen menschlichen Integrator, der:
1. Die Outputs verschiedener Modelle synthesiert
2. Widersprüche auflöst
3. Fehler erkennt und korrigiert
4. Die philosophische Kohärenz wahrt

v50.7 zeigt: **Verteilte Entwicklung ist möglich** – aber nicht einfach, und nicht ohne menschliche Urteilskraft.

---

### Danksagung an die Tools

**Google Cloud Platform:** Hosting (Cloud Run), Datenbank (Firestore), Embedding API  
**Streamlit:** UI-Framework für schnelles Prototyping  
**Python-Ökosystem:** rank-bm25, pymupdf, beautifulsoup4, pandas  
**Open-Source-Community:** Ohne die Arbeit Tausender Entwickler wäre diese Engine unmöglich

---

## 12.2 Git-Workflow

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
git tag v50.9
git push origin v50.9
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
docs: Update FIBEL with v50.8 changes
```

---

## 12.3 Glossar

**BM25:** Keyword-basierter Retrieval-Algorithmus (Best Match 25)

**Chunk:** Textsegment (typisch 300-500 Tokens), das als atomare Einheit indiziert wird

**Essence Parity:** Fairness-Mechanismus (logarithmische Chunk-Berechnung)

**Enforcer:** Validierungs-Modul (zwei Ebenen: hermeneutisch + Validität)

**Gini Coefficient:** Maß für Ungleichheit (0 = perfekt fair, 1 = maximal unfair)

**Hermeneutic Router:** Intent-Klassifizierungs-Modul (LITERARY, FACTUAL, ANALYTICAL)

**Investigativ-Modus:** Retrieval-Strategie für kleine Korpora (≤5 Dokumente)

**RRF (Reciprocal Rank Fusion):** Algorithmus zur Kombination mehrerer Rankings

**VIP-Schutz:** Fairness-Mechanismus (garantiert top-3 Chunks pro ausgewähltem Dokument)

---

## 12.4 Kontakt & Support

**Projekt-Lead:** Grigori Pantijelew  
**Projekt-Email:** hermeneutic-engine@proton.me

**Repository:** https://github.com/gpantijelew/hermeneutic-engine (wird mit v50.9 public)

**Support:**
- GitHub Issues (nach Public Release)
- Email für Fragen und Kollaborations-Anfragen

**Response-Zeit:** 1-3 Tage (dies ist ein Forschungsprojekt, kein kommerzielles Produkt)

---

**Ende der FIBEL v50.9**

**Status:** Vollständig (Sections 1-12) ✅  
**Letzte Aktualisierung:** 16. Februar 2026  
**Version:** v50.9 "Public Launch"

**Nächster Schritt:** GitHub-Release + Community-Feedback