import re
import os
import logging
from google import genai
from typing import List, Set
from modules.config import MODEL_QUESTION_CONV

logger = logging.getLogger(__name__)

def post_process_synthesis(synthesis_text: str, used_source_ids: List[int]) -> str:
    """
    Hauptfunktion: Bereinigt die Synthese nach der LLM-Generierung.
    1. Entfernt Fragmente (< 7 Wörter).
    2. Konvertiert Fragen in Aussagen (Batch-Processing).
    3. Entfernt ungültige Zitationen (die nicht in used_source_ids sind).
    4. v49.1 FIX: Robust gegen Placeholder-Fehler.
    5. v49.2 FIX: Speaker-Header werden NICHT als Fragmente entfernt!
    6. v50.10 FIX: Ranking-Zeilen (Platz X) werden behalten!
    """
    if not synthesis_text:
        return ""

    lines = synthesis_text.split('\n')
    questions_to_convert = []

    # Set für schnelleren Lookup
    valid_ids = set(used_source_ids)

    # 1. Erster Pass: Fragmente filtern & Fragen sammeln
    temp_lines = []
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            temp_lines.append("") # Leerzeilen behalten
            continue

        # Überschriften behalten (starten mit #)
        if stripped_line.startswith('#'):
            temp_lines.append(stripped_line)
            continue

        # Citation-Check & Cleanup
        def validate_match(match):
            try:
                cit_id = int(match.group(1))
                if cit_id in valid_ids:
                    return f"[{cit_id}]"
            except ValueError:
                pass
            return "" # Ungültige Citation entfernen

        line_validated = re.sub(r'\[(\d+)\]', validate_match, stripped_line)

        # Fragment-Check (Länge ohne Citations)
        text_only = re.sub(r'\[\d+\]', '', line_validated).strip()
        # Ignoriere Aufzählungszeichen für den Count
        text_only_clean = re.sub(r'^[\-\*\d\.]+\s*', '', text_only)

        # Toleranz: 7 Wörter Minimum für echte Sätze
        if len(text_only_clean.split()) < 7:
            # WHITELIST 1: Speaker-Header (markdown bold: **Name**)
            is_speaker_header = (
                stripped_line.startswith('**') and 
                stripped_line.endswith('**') and
                len(stripped_line.strip('*').strip()) < 50
            )

            # WHITELIST 2: Überschriften mit Doppelpunkt
            is_heading = text_only_clean.endswith(':')

            # WHITELIST 3: Markdown-Überschriften (### Name)
            is_markdown_heading = stripped_line.startswith('###')

            # --- NEU: WHITELIST 4: Ranking/Struktur-Zeilen ---
            # Entferne Sternchen und mache klein für den Check
            clean_start = stripped_line.replace('*', '').strip().lower()
            is_ranking = (
                clean_start.startswith('platz') or 
                clean_start.startswith('rang') or 
                clean_start.startswith('rank') or
                clean_start.startswith('text') or   # z.B. "Text 1: ..."
                clean_start.startswith('quelle')    # z.B. "Quelle A: ..."
            )

            # Wenn Whitelist-Match → BEHALTEN!
            if is_speaker_header:
                temp_lines.append(stripped_line)
                continue

            if is_heading:
                temp_lines.append(line_validated)
                continue

            if is_markdown_heading:
                temp_lines.append(stripped_line)
                continue

            if is_ranking:
                # logger.info(f"✅ Ranking-Zeile behalten: '{stripped_line}'")
                temp_lines.append(stripped_line)
                continue

            # Sonst: Fragment entfernen
            logger.warning(f"Fragment entfernt: '{text_only_clean}'")
            continue

        # Frage-Check
        if text_only.endswith('?'):
            questions_to_convert.append(line_validated)
            temp_lines.append(f"__QUESTION_PLACEHOLDER_{len(questions_to_convert)-1}__")
        else:
            temp_lines.append(line_validated)

    # 2. Batch-Konvertierung von Fragen
    converted_statements = []
    if questions_to_convert:
        converted_statements = _batch_convert_questions(questions_to_convert)

    # 3. Zusammenbau
    final_lines = []
    for line in temp_lines:
        if "__QUESTION_PLACEHOLDER_" in line:
            match = re.search(r'__QUESTION_PLACEHOLDER_(\d+)__', line)
            if match:
                try:
                    idx = int(match.group(1))
                    if 0 <= idx < len(converted_statements):
                        final_lines.append(converted_statements[idx])
                    elif 0 <= idx < len(questions_to_convert):
                        final_lines.append(questions_to_convert[idx])
                    else:
                        continue
                except ValueError:
                    continue
            else:
                continue
        else:
            final_lines.append(line)

    # Doppelte Leerzeilen entfernen
    result = '\n'.join(final_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    result = re.sub(r'> \*\*Thinking:\*\*.*?(?=\n\n|\Z)', '', result, flags=re.DOTALL)

    return result.strip()

def _batch_convert_questions(questions: List[str]) -> List[str]:
    """
    Konvertiert eine Liste von Fragen in Aussagen via LLM (Flash Model).
    """
    if not questions:
        return []
    try:
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        prompt = "Formuliere die folgenden rhetorischen Fragen in neutrale Aussagen um. Behalte alle Quellenangaben [x] exakt bei.\n\n"
        for i, q in enumerate(questions):
            prompt += f"Frage {i}: {q}\n"
        prompt += "\nAntwortformat:\nAussage 0: ...\nAussage 1: ...\n(usw.)"

        response = client.models.generate_content(
            model=MODEL_QUESTION_CONV,
            contents=prompt
        )
        text = response.text
        statements = []
        for i in range(len(questions)):
            match = re.search(f"Aussage {i}:\\s*(.*)", text)
            if match:
                statements.append(match.group(1).strip())
            else:
                statements.append(questions[i])
        return statements
    except Exception as e:
        logger.error(f"Fehler bei Frage-Konvertierung: {e}")
        return questions # Fallback: Originale zurückgeben
