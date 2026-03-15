# 🤝 Contributing to Hermeneutic Engine

Thank you for your interest in this project! The Hermeneutic Engine is a **research prototype** that has been **production-ready** since v50.9 (February 2026) and is publicly available.

---

## 🎯 Project Philosophy

This project is **not** a standard RAG tool, but a **specialized research instrument**. Contributions should respect this philosophy:

- ✅ **Depth over Breadth**: Hermeneutic precision matters more than features
- ✅ **Quality over Quantity**: Small, curated datasets
- ✅ **Reproducibility**: All changes must be scientifically traceable
- ❌ **No Feature Creep**: New features only if they support the core mission

---

## 🚀 How You Can Contribute

### 1. Bug Reports

**Before reporting a bug:**
- Check if the bug is already reported in [Issues](../../issues)
- Make sure you're using the latest version (`git pull`)
- Test if the bug occurs in a fresh virtual environment

**What makes a good bug report:**
```markdown
**Description:**
Brief description of the problem

**Steps to Reproduce:**
1. Go to "Analysis Tab"
2. Enter query "..."
3. Observe error X

**Expected Behavior:**
What should happen?

**Actual Behavior:**
What happens instead?

**Environment:**
- OS: Windows 11 / macOS 14 / Ubuntu 24
- Python: 3.11+
- Streamlit: 1.50.0
- Hermeneutic Engine: v50.9

**Logs:**
```python
# Paste relevant logs/tracebacks here
```
```

---

### 2. Feature Requests

**Please note:**
- New features must support the **core mission** (hermeneutic analysis, not general-purpose RAG)
- Features that want to make the engine "like NotebookLM" will be declined
- Features must be **scientifically justifiable**

**What makes a good feature request:**
```markdown
**Use Case:**
What research problem does this feature solve?

**Methodological Justification:**
Why is this feature important for hermeneutic analysis?

**Alternative Solutions:**
What other approaches have you considered?

**Example:**
Show a concrete example where the feature would help
```

---

### 3. Code Contributions

#### Prerequisites

- Basic knowledge of Python 3.11+
- Understanding of RAG systems
- Familiarity with Streamlit (for UI changes)
- Understanding of hermeneutic methods (ideally)

#### Development Setup

```bash
# 1. Fork the repository
# 2. Clone your fork
git clone https://github.com/YOUR-USERNAME/hermeneutic-engine.git
cd hermeneutic-engine

# 3. Create a branch
git checkout -b feature/your-feature-name

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env  # If available
# Add your GEMINI_API_KEY

# 6. Test the app
streamlit run app.py
```

#### Code Conventions

**Python Style:**
- Follow [PEP 8](https://pep8.org/)
- Use type hints where possible
- Docstrings for all public functions

**Example:**
```python
def calculate_confidence_scores(
    query_vector: List[float], 
    results: List[Dict]
) -> List[Dict]:
    """
    Adds a confidence score to each result.
    
    Args:
        query_vector: Embedding vector of the query
        results: List of retrieval results
    
    Returns:
        Sorted list with confidence scores (0-100)
    """
    # Implementation...
```

**Commit Messages:**
```bash
# Format: <type>: <subject>
# Types: feat, fix, docs, style, refactor, test, chore

git commit -m "feat: Add parallel validation to Enforcer"
git commit -m "fix: Correct RRF k-parameter calculation"
git commit -m "docs: Update FIBEL with v50.9 changes"
```

---

#### Testing

**Before creating a pull request:**

1. **Test your changes locally:**
   ```bash
   # Startup test
   python -m modules.config
   
   # Feature test
   streamlit run app.py
   # Manually test: Chat, Import, Analysis
   ```

2. **Check for regressions:**
   - Old features must continue to work
   - Test at minimum: Chat, Import (HTML), RAG Analysis

3. **Code quality:**
   ```bash
   # Optional: Use linters
   flake8 modules/
   mypy modules/  # For type checking
   ```

---

#### Pull Request Process

1. **Update your documentation:**
   - Add new features to `README.md`
   - Update `FIBEL_v50_8.md` with technical details
   - Add docstrings in the code

2. **Create the PR:**
   ```markdown
   **What does this PR change?**
   Brief description (1-2 sentences)
   
   **Why is this change necessary?**
   Methodological justification
   
   **How was it tested?**
   - [ ] Startup test successful
   - [ ] Feature X tested
   - [ ] No regressions
   
   **Breaking changes?**
   Yes/No - If yes, which ones?
   ```

3. **Review process:**
   - The Project Lead (Grigori) reviews all PRs
   - Change requests will be added as review comments
   - After approval, the PR will be merged

---

### 4. Documentation Contributions

**Documentation is just as important as code!**

**What you can improve:**
- Typos/grammar in README.md or FIBEL
- Missing explanations for complex features
- Examples for use cases
- Translations (e.g., README in other languages)

**Process:**
1. Edit the Markdown file directly
2. Create a PR with clear description
3. No tests needed for pure documentation changes

---

## 🔬 Special Areas for Contributions

### A) Importers for New Platforms

**Wanted:** Parsers for additional chat platforms

**What you need:**
1. HTML export from the platform
2. Basic knowledge of BeautifulSoup
3. Understanding of the importer architecture

**How to add a new importer:**

```python
# modules/importers/html/your_platform.py

from modules.importers.base import BaseImporter
from bs4 import BeautifulSoup

class YourPlatformImporter(BaseImporter):
    platform_name = "Your Platform"
    
    # Signatures for auto-detection
    signatures = [
        'data-platform="your-platform"',
        'class="your-platform-message"'
    ]
    
    def parse(self, html_content, container=None):
        soup = BeautifulSoup(html_content, 'html.parser')
        messages = []
        
        # Find all message blocks
        for msg_block in soup.find_all('div', class_='message'):
            role = 'user' if 'user-message' in msg_block.get('class', []) else 'model'
            content = msg_block.find('span', class_='content').get_text()
            
            messages.append({
                'role': role,
                'content': content
            })
        
        return messages
```

**Register the importer:**
```python
# modules/importers/__init__.py

from .html.your_platform import YourPlatformImporter

IMPORTERS = {
    # ... existing importers
    'your_platform': YourPlatformImporter,
}
```

---

### B) New Enforcer Categories

**Currently (v50.9), the Enforcer uses Two-Dimensional Validation:**

**Dimension 1 (Hermeneutics – How is it said?):**
- Quote (Direct quotation)
- Paraphrase (Reformulation)
- Inference (Logical derivation)

**Dimension 2 (Validity – Is it correct?):**
- Supported (Source confirms)
- Neutral (Source is silent)
- Contradiction (Source contradicts)

**You could add additional dimensions or categories, e.g.:**
- **TEMPORAL**: Time-related statement (must be validated with dates)
- **NUMERICAL**: Numerical statement (must be exact)
- **COMPARATIVE**: Comparative statement (multiple sources involved)

**Instructions:**
1. Extend `modules/hermeneutic_enforcer.py` (adapt prompt)
2. Update Decision Matrix (ensure logical consistency)
3. Test with edge cases

---

### C) Performance Optimizations

**Known bottlenecks:**
- BM25 Index Rebuild (slow with >10k chunks)
- Enforcer with >100 sentences (even with parallelization)
- Embedding creation for large imports

**If you're a performance expert:**
- Profiling with `cProfile`
- Suggestions for caching strategies
- Optimizations for Firestore queries

---

## 🚫 What We Don't Accept

❌ **Features that dilute the core mission:**
- "I want to index 1 million documents" → This is not our use case
- "I want to analyze audio/video" → Out of scope
- "I want a general knowledge management tool" → Use NotebookLM

❌ **Breaking changes without discussion:**
- No major refactorings without prior issue discussion
- No changes to the core architecture (Triad) without justification

❌ **Code without tests:**
- New features must be manually testable
- If possible: Add unit tests (not mandatory yet, but recommended)

---

## 📚 Resources for Contributors

**Technical Documentation:**
- [FIBEL v50.9](docs/FIBEL_v50_8.md) – Complete technical specs (100+ pages)
- [Model Config](modules/config.py) – Central model mapping
- [Importer Architecture](modules/importers/README.md) – How parsers work

**Best Practices:**
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Streamlit Docs](https://docs.streamlit.io/)
- [Firestore Best Practices](https://cloud.google.com/firestore/docs/best-practices)

---

## 💬 Questions?

**Contact:**
- **GitHub Issues:** For technical questions
- **Email:** hermeneutic-engine@proton.me

**Please note:**
- Responses may take 1-3 days (this is a research project, not a commercial product)
- For urgent bugs: Mark issue with `critical` label

---

## 🙏 Thank You!

Every contribution – whether code, documentation, or bug report – helps improve this research tool.

**Special thanks to:**
- Everyone who reports issues
- Everyone who corrects typos
- Everyone who recommends the project

**Your name could be here!** 🌟

---

**Version:** v50.9  
**Last Updated:** February 16, 2026
