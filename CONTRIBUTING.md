# 🤝 Contributing to Hermeneutic Engine

Danke für dein Interesse an diesem Projekt! Die Hermeneutic Engine ist ein **Forschungsprototyp**, der sich noch in aktiver Entwicklung befindet.

---

## 🎯 Projekt-Philosophie

Dieses Projekt ist **kein** Standard-RAG-Tool, sondern ein **spezialisiertes Forschungswerkzeug**. Beiträge sollten diese Philosophie respektieren:

- ✅ **Tiefe über Breite**: Hermeneutische Präzision wichtiger als Features
- ✅ **Qualität über Quantität**: Kleine, kuratierte Datenmengen
- ✅ **Reproduzierbarkeit**: Alle Änderungen müssen wissenschaftlich nachvollziehbar sein
- ❌ **Keine Feature-Creep**: Neue Features nur, wenn sie die Kern-Mission unterstützen

---

## 🚀 Wie du beitragen kannst

### 1. Bug Reports

**Bevor du einen Bug meldest:**
- Prüfe, ob der Bug schon in [Issues](../../issues) gemeldet wurde
- Stelle sicher, dass du die neueste Version nutzt (`git pull`)
- Teste, ob der Bug auch in einem frischen Virtual Environment auftritt

**Was in einen guten Bug Report gehört:**
```markdown
**Beschreibung:**
Kurze Beschreibung des Problems

**Reproduktion:**
1. Gehe zu "Analyse-Tab"
2. Stelle Query "..."
3. Beobachte Fehler X

**Expected Behavior:**
Was sollte passieren?

**Actual Behavior:**
Was passiert stattdessen?

**Environment:**
- OS: Windows 11 / macOS 14 / Ubuntu 24
- Python: 3.13.1
- Streamlit: 1.50.0
- Hermeneutic Engine: v49.2

**Logs:**
```python
# Füge relevante Logs/Tracebacks hier ein
```
```

---

### 2. Feature Requests

**Bitte beachte:**
- Neue Features müssen die **Kern-Mission** unterstützen (hermeneutische Analyse, nicht allgemeines RAG)
- Features, die die Engine "wie NotebookLM" machen wollen, werden abgelehnt (das ist bereits gelöst!)
- Features müssen **wissenschaftlich begründbar** sein

**Was in einen guten Feature Request gehört:**
```markdown
**Use-Case:**
Welches Forschungsproblem löst dieses Feature?

**Methodologische Begründung:**
Warum ist dieses Feature für hermeneutische Analyse wichtig?

**Alternative Lösungen:**
Welche anderen Ansätze hast du in Betracht gezogen?

**Beispiel:**
Zeige ein konkretes Beispiel, wo das Feature helfen würde
```

---

### 3. Code Contributions

#### Voraussetzungen

- Grundkenntnisse in Python 3.13+
- Verständnis für RAG-Systeme
- Kenntnisse in Streamlit (für UI-Änderungen)
- Verständnis für hermeneutische Methoden (idealerweise)

#### Development Setup

```bash
# 1. Fork das Repo
# 2. Clone deinen Fork
git clone https://github.com/DEIN-USERNAME/hermeneutic-engine.git
cd hermeneutic-engine

# 3. Erstelle einen Branch
git checkout -b feature/dein-feature-name

# 4. Installiere Dependencies
pip install -r requirements.txt

# 5. Konfiguriere Environment
cp .env.example .env  # Falls vorhanden
# Füge deinen GEMINI_API_KEY hinzu

# 6. Teste die App
streamlit run app.py
```

#### Code-Konventionen

**Python-Style:**
- Folge [PEP 8](https://pep8.org/)
- Nutze Type Hints wo möglich
- Docstrings für alle öffentlichen Funktionen

**Beispiel:**
```python
def calculate_confidence_scores(
    query_vector: List[float], 
    results: List[Dict]
) -> List[Dict]:
    """
    Fügt jedem Ergebnis einen Confidence Score hinzu.
    
    Args:
        query_vector: Embedding-Vektor der Query
        results: Liste von Retrieval-Ergebnissen
    
    Returns:
        Sortierte Liste mit Confidence Scores (0-100)
    """
    # Implementation...
```

**Commit-Messages:**
```bash
# Format: <type>: <subject>
# Typen: feat, fix, docs, style, refactor, test, chore

git commit -m "feat: Add parallel validation to Enforcer"
git commit -m "fix: Correct RRF k-parameter calculation"
git commit -m "docs: Update FIBEL with v49.2 changes"
```

---

#### Testing

**Bevor du einen Pull Request erstellst:**

1. **Teste deine Änderungen lokal:**
   ```bash
   # Startup-Test
   python -m modules.config
   
   # Feature-Test
   streamlit run app.py
   # Manuell testen: Chat, Import, Analyse
   ```

2. **Prüfe auf Regressions:**
   - Alte Features müssen weiter funktionieren
   - Teste mindestens: Chat, Import (HTML), RAG-Analyse

3. **Code-Qualität:**
   ```bash
   # Optional: Nutze Linter
   flake8 modules/
   mypy modules/  # Für Type-Checking
   ```

---

#### Pull Request Process

1. **Update deine Dokumentation:**
   - Füge neue Features zu `README.md` hinzu
   - Update `FIBEL_v49.2.md` mit technischen Details
   - Füge Docstrings im Code hinzu

2. **Erstelle den PR:**
   ```markdown
   **Was ändert dieser PR?**
   Kurze Beschreibung (1-2 Sätze)
   
   **Warum ist diese Änderung nötig?**
   Methodologische Begründung
   
   **Wie wurde es getestet?**
   - [ ] Startup-Test erfolgreich
   - [ ] Feature X getestet
   - [ ] Keine Regressions
   
   **Breaking Changes?**
   Ja/Nein - Falls ja, welche?
   ```

3. **Review-Prozess:**
   - Der Project Lead (Grigori) reviewed alle PRs
   - Änderungswünsche werden als Review-Comments hinzugefügt
   - Nach Approval wird der PR gemerged

---

### 4. Dokumentations-Beiträge

**Dokumentation ist genauso wichtig wie Code!**

**Was du verbessern kannst:**
- Typos/Grammatik in README.md oder FIBEL
- Fehlende Erklärungen zu komplexen Features
- Beispiele für Use-Cases
- Übersetzungen (z.B. README in andere Sprachen)

**Prozess:**
1. Bearbeite die Markdown-Datei direkt
2. Erstelle einen PR mit klarer Beschreibung
3. Keine Tests nötig für reine Docs-Änderungen

---

## 🔬 Spezielle Bereiche für Beiträge

### A) Importer für neue Plattformen

**Gesucht:** Parser für weitere Chat-Plattformen

**Was du brauchst:**
1. HTML-Export von der Plattform
2. Grundkenntnisse in BeautifulSoup
3. Verständnis für die Importer-Architektur

**So fügst du einen neuen Importer hinzu:**

```python
# modules/importers/html/deine_plattform.py

from modules.importers.base import BaseImporter
from bs4 import BeautifulSoup

class DeinePlattformImporter(BaseImporter):
    platform_name = "Deine Plattform"
    
    # Signaturen für Auto-Detection
    signatures = [
        'data-platform="deine-plattform"',
        'class="deine-plattform-message"'
    ]
    
    def parse(self, html_content, container=None):
        soup = BeautifulSoup(html_content, 'html.parser')
        messages = []
        
        # Finde alle Nachrichten-Blöcke
        for msg_block in soup.find_all('div', class_='message'):
            role = 'user' if 'user-message' in msg_block.get('class', []) else 'model'
            content = msg_block.find('span', class_='content').get_text()
            
            messages.append({
                'role': role,
                'content': content
            })
        
        return messages
```

**Registriere den Importer:**
```python
# modules/importers/__init__.py

from .html.deine_plattform import DeinePlattformImporter

IMPORTERS = {
    # ... bestehende Importer
    'deine_plattform': DeinePlattformImporter,
}
```

---

### B) Neue Enforcer-Kategorien

**Aktuell gibt es 4 Kategorien:**
- Paraphrase
- Meta-Aussage
- Inferenz
- Halluzination

**Du könntest neue hinzufügen, z.B.:**
- **QUOTATION**: Direktes Zitat (muss wörtlich übereinstimmen)
- **TEMPORAL**: Zeitbezogene Aussage (muss mit Datum validiert werden)
- **NUMERICAL**: Zahlen-Aussage (muss exakt sein)

**Anleitung:**
1. Erweitere `modules/hermeneutic_enforcer.py` (Prompt anpassen)
2. Update `modules/llm_instructions.py` (neue Kategorie dokumentieren)
3. Teste mit Edge-Cases

---

### C) Performance-Optimierungen

**Bekannte Bottlenecks:**
- BM25 Index Rebuild (bei >10k Chunks langsam)
- Enforcer bei >100 Sätzen (selbst mit Parallelisierung)
- Embedding-Erstellung für große Importe

**Wenn du Performance-Experte bist:**
- Profiling mit `cProfile`
- Vorschläge für Caching-Strategien
- Optimierungen für Firestore-Queries

---

## 🚫 Was wir NICHT akzeptieren

❌ **Features, die die Kern-Mission verwässern:**
- "Ich möchte 1 Million Dokumente indizieren" → Das ist nicht unser Use-Case
- "Ich möchte Audio/Video analysieren" → Außerhalb des Scopes
- "Ich möchte ein allgemeines Wissensmanagement-Tool" → Nutze NotebookLM

❌ **Breaking Changes ohne Diskussion:**
- Keine großen Refactorings ohne vorherige Issue-Diskussion
- Keine Änderungen an der Kern-Architektur (Triade) ohne Begründung

❌ **Code ohne Tests:**
- Neue Features müssen manuell testbar sein
- Falls möglich: Unit Tests hinzufügen (noch nicht Pflicht, aber empfohlen)

---

## 📚 Ressourcen für Mitwirkende

**Technische Dokumentation:**
- [FIBEL v49.2](FIBEL_Hermeneutic_Engine_v49.md) – Vollständige technische Specs
- [Model-Config](modules/config.py) – Zentrale Model-Zuordnung
- [Importer-Architektur](modules/importers/README.md) – Wie Parser funktionieren

**Wissenschaftlicher Hintergrund:**
- **Hermeneutik:** Gadamer, "Wahrheit und Methode" (1960)
- **RAG-Systeme:** Lewis et al., "Retrieval-Augmented Generation" (2020)
- **LLM-Philosophie:** Bender & Koller, "Climbing towards NLU" (2020)

**Best Practices:**
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Streamlit Docs](https://docs.streamlit.io/)
- [Firestore Best Practices](https://cloud.google.com/firestore/docs/best-practices)

---

## 💬 Fragen?

**Kontakt:**
- **GitHub Issues:** Für technische Fragen
- **Email:** hermeneutic-engine@proton.me

**Bitte beachte:**
- Responses können 1-3 Tage dauern (dies ist ein Forschungsprojekt, kein kommerzielles Produkt)
- Für dringende Bugs: Markiere Issue mit Label `critical`

---

## 🙏 Danke!

Jeder Beitrag – ob Code, Dokumentation oder Bug Report – hilft, dieses Forschungswerkzeug zu verbessern.

**Besonderer Dank an:**
- Alle, die Issues melden
- Alle, die Typos korrigieren
- Alle, die das Projekt weiterempfehlen

**Dein Name könnte hier stehen!** 🌟

---

**Version:** v49.2  
**Stand:** 26. Dezember 2025
