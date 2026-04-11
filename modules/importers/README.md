# Importers Module (v47)

Dieses Modul handhabt den Import von Chat-Verläufen aus verschiedenen Quellen.

## Struktur

- `base.py`: Basis-Klassen (`BaseImporter`, `HTMLImporter`, `ConfigBasedImporter`) und Konfiguration (`PARSER_CONFIGS`).
- `utils.py`: Hilfsfunktionen (`detect_platform`, `get_topic_summary`).
- `text_parser.py`: Fallback-Parser, der LLMs nutzt, um unstrukturierten Text zu zerlegen.
- `html/`: Parser für HTML-Exporte (ChatGPT, Gemini, Claude, etc.).
- `documents/`: Parser für Dokumente (PDF, ePub, fb2, markdown).

## Neuen Importer hinzufügen

1. **HTML-basiert (einfach):**
   - Füge Eintrag in `PARSER_CONFIGS` in `base.py` hinzu.
   - Erstelle Klasse in `html/` (erbt von `ConfigBasedImporter`).
   - Registriere in `__init__.py`.

2. **Spezial-Logik:**
   - Erstelle Klasse (erbt von `HTMLImporter` oder `BaseImporter`).
   - Implementiere `parse()` und `import_to_firestore()`.
   - Registriere in `__init__.py`.