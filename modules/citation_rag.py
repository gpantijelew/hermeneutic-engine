# modules/citation_rag.py - v50.9: DATE HEADER FIX
import logging
import json
import re
import os
import time
import asyncio
from functools import partial
from collections import defaultdict
import google.generativeai as genai
from typing import List, Dict, Any, Tuple, Optional

from modules.config import (
    MODEL_SYNTHESIS,
    MODEL_QUERY_EXPANSION,
    MODEL_ENFORCER
)

from modules.vector_store import FirestoreVectorStore
from modules.evidence_synthesis import EvidenceFirstSynthesizer
from modules.llm_instructions import ENFORCER_INSTRUCTION
from modules.llm_instructions import EXEGESIS_SYNTHESIS_PROMPT, SYNTHESIS_INSTRUCTION
from modules.hermeneutic_reranker import HermeneuticReranker
from modules.hermeneutic_router import HermeneuticRouter
from types import SimpleNamespace
from datetime import datetime

logger = logging.getLogger(__name__)


class CitationRAG:
    def __init__(self, vector_store: FirestoreVectorStore = None, model_name: str = MODEL_SYNTHESIS):
        if vector_store is None:
            from google.cloud import firestore
            db = firestore.Client()
            vector_store = FirestoreVectorStore(db)

        self.vector_store = vector_store
        self.model_name = model_name
        self.router = HermeneuticRouter()
        self.synthesizer = EvidenceFirstSynthesizer(model_name)

        # UI-Zugriff für Imbalance-Daten
        self.last_imbalance_info = None 

        self.current_context = {
            "intent": "FACTUAL",
            "threshold": 0.65
        }

        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)

    def expand_query_multilingual(self, query: str) -> str:
        """v50.1: Query Translation für multilingualen Retrieval."""
        try:
            model = genai.GenerativeModel(MODEL_QUERY_EXPANSION)

            prompt = f"""
Du bist ein Such-Optimierer für multilingualen Retrieval.

USER QUERY (Original): "{query}"

AUFGABE: Übersetze diese Query in folgende Sprachen:
1. Englisch
2. Russisch (Kyrillisch)
3. Französisch

OUTPUT-FORMAT: Original + 3 Übersetzungen, durch Leerzeichen getrennt.

BEISPIEL:
Input: "Wie definiert Adorno den Essay?"
Output: "Wie definiert Adorno den Essay? How does Adorno define the essay? Как Адорно определяет эссе? Comment Adorno définit-il l'essai?"

WICHTIG: 
- Nur die Übersetzungen, kein Präambel!
- Trenne mit Leerzeichen, nicht mit Zeilenumbrüchen!
- Behalte Namen unverändert!
"""

            response = model.generate_content(prompt, request_options={'timeout': 5})
            multilingual_query = response.text.strip()
            multilingual_query = re.sub(r'\n+', ' ', multilingual_query)

            logger.info(f"🌐 Query Translation: {query[:50]}... → {len(multilingual_query.split())} words")

            return multilingual_query

        except Exception as e:
            logger.warning(f"⚠️ Query Translation fehlgeschlagen: {e}. Fallback auf Original.")
            return query

    def retrieve_with_rrf(
        self, 
        query: str, 
        limit: int = 15, 
        chat_id: Any = None, 
        use_router: bool = True
    ) -> List[Dict]:
        """v50.1: Retrieval mit Router, RRF und Query-Translation."""
        if use_router:
            try:
                route = self.router.route_query(query)
                dynamic_limit = route["limit"]
                intent = route["intent"]
                threshold = route["threshold"]

                logger.info(f"🚀 Retrieval Mode: AUTO ({intent}) | Limit: {dynamic_limit} | Threshold: {threshold}")
            except Exception as e:
                logger.error(f"❌ Router Error: {e}. Fallback auf Standard-Parameter.")
                dynamic_limit = limit
                intent = "FALLBACK"
                threshold = 0.65
        else:
            dynamic_limit = limit
            intent = "MANUAL"
            threshold = 0.65
            logger.info(f"🔧 Retrieval Mode: MANUAL | Limit: {dynamic_limit}")

        if chat_id:
            old_limit = dynamic_limit
            dynamic_limit = max(dynamic_limit, 70)

            if dynamic_limit > old_limit:
                logger.info(f"📈 Selection Boost: Limit erhöht von {old_limit} auf {dynamic_limit}")

        self.current_context = {"intent": intent, "threshold": threshold}

        expanded_query = self.expand_query_multilingual(query)

        allowed_ids = chat_id if isinstance(chat_id, list) else [chat_id] if chat_id else None

        results, _ = self.vector_store.hybrid_search(
            query=expanded_query,
            limit=dynamic_limit,
            allowed_chat_ids=allowed_ids
        )

        return results

    def extract_keywords(self, query: str) -> List[str]:
        """Legacy-Funktion."""
        clean_query = query.replace("-", " ").replace("_", " ")
        ignore = {
            'wie', 'was', 'wo', 'und', 'oder', 'der', 'die', 'das', 
            'bei', 'mit', 'von', 'über', 'ist', 'sind', 'jeweils', 
            'erwähnung', 'auf', 'den', 'dem', 'sagen', 'meinen'
        }

        keywords = []
        for w in clean_query.split():
            w_clean = w.lower().strip('?".,!:')
            if w_clean not in ignore and len(w_clean) > 2:
                keywords.append(w_clean)

        return keywords

    def clean_citation_format(self, text: str) -> str:
        """Bereinigt Zitationsformate."""
        text = re.sub(r'\[source_id:\s*(\d+)\]', r'[\1]', text)
        text = re.sub(r'\[Quelle:\s*(\d+)\]', r'[\1]', text)
        return text

    def _get_chat_title(self, chat_id: str) -> str:
        """v50.2: Hole echten Chat-Titel (Fallback-sicher)."""
        try:
            from google.cloud import firestore
            db = firestore.Client()
            chat_doc = db.collection('chats').document(chat_id).get()
            if chat_doc.exists:
                return chat_doc.to_dict().get('title', f'Doc {chat_id[-8:]}')
            else:
                return f'Doc {chat_id[-8:]}'
        except Exception as e:
            return f'Doc {chat_id[-8:]}'

    def extract_date_from_metadata(self, res: Dict) -> datetime:
           """
           Extrahiert Datum aus Chunk-Metadaten für chronologische Sortierung.

           Unterstützt Formate:
           - "04.12.2025" (Tag.Monat.Jahr)
           - "Mai 2025" (Monat Jahr)
           - "13.10.2025" (Tag.Monat.Jahr)

           Returns:
                 datetime-Objekt oder datetime.min falls kein Datum
           """
           meta = res.get('metadata', {})
           date_str = meta.get('real_date_str', '')

           if not date_str or date_str == 'o.D.':
                 return datetime.min

           try:
                 # Format: "04.12.2025"
                 if '.' in date_str:
                      return datetime.strptime(date_str, "%d.%m.%Y")

                 # Format: "Mai 2025"
                 elif ' ' in date_str:
                      month_map = {
                              'Januar': 1, 'Februar': 2, 'März': 3, 'April': 4,
                              'Mai': 5, 'Juni': 6, 'Juli': 7, 'August': 8,
                              'September': 9, 'Oktober': 10, 'November': 11, 'Dezember': 12
                      }
                      parts = date_str.split()
                      if len(parts) == 2 and parts[0] in month_map:
                              month = month_map[parts[0]]
                              year = int(parts[1])
                              return datetime(year, month, 1)

           except Exception as e:
                 logger.warning(f"⚠️ Konnte Datum nicht parsen: '{date_str}' → {e}")

           return datetime.min

    def generate_answer(
        self, 
        query: str, 
        results: List[Dict],
        strict_parity: bool = False
    ) -> Tuple[str, List[Dict], str]:
        """
        v50.9: ESSENCE PARITY - Intelligente Essenz-Extraktion.

        Max 12 Chunks pro Dokument (Code-Limit) + Erzwungene Zitat-Quota (Prompt).
        """
        if not results:
            return "Ich habe keine relevanten Informationen in den Dokumenten gefunden.", [], "unknown"

        intent = self.current_context.get("intent", "FACTUAL")
        rerank_threshold = self.current_context.get("threshold", 0.65)

        # Extrahiere chat_id aus results
        chat_id = None
        if results:
            first_result_chat_ids = [r.get('chat_id') for r in results if r.get('chat_id')]
            if first_result_chat_ids:
                unique_chat_ids = list(set(first_result_chat_ids))
                if len(unique_chat_ids) <= 10:
                    chat_id = unique_chat_ids

        # --- Scoring ---
        is_rrf_result = any(res.get('_rrf_active') for res in results)

        if is_rrf_result:
            logger.info("⚡ RRF-Ranking erkannt.")
            for res in results:
                if '_final_score' not in res:
                    res['_final_score'] = res.get('score', 0.0)
        else:
            for res in results:
                res['_final_score'] = res.get('score', 0.0) + res.get('_keyword_boost', 0.0)
            results.sort(key=lambda x: x.get('_final_score', 0), reverse=True)

        # --- Reranking ---
        top_candidates = results[:100]

        logger.info(f"⚖️ Reranking mit Threshold: {rerank_threshold} (Intent: {intent})")

        reranker = HermeneuticReranker(threshold=rerank_threshold)
        top_results, rerank_stats = reranker.rerank(query, top_candidates, max_results=70)

        if len(top_results) < 5:
            logger.warning(f"⚠️ Zu wenig Treffer nach Reranking ({len(top_results)}). Senke Threshold auf 0.35...")
            reranker_relaxed = HermeneuticReranker(threshold=0.35)
            top_results, _ = reranker_relaxed.rerank(query, top_candidates, max_results=70)

        # --- Diagnostik VOR Essenz-Extraktion ---
        surviving_docs = defaultdict(int)
        for res in top_results:
            chat_id_single = res.get('chat_id', 'unknown')
            chat_title = res.get('metadata', {}).get('chat_title') or self._get_chat_title(chat_id_single)
            surviving_docs[chat_title] += 1

        logger.info(f"📊 Dokumente nach Reranking (vor Essenz-Extraktion):")
        for doc_title, count in sorted(surviving_docs.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  📄 {doc_title}: {count} Chunks")

        # --- v50.5 FIX: Imbalance-Daten für UI speichern ---
        if surviving_docs:
            counts = list(surviving_docs.values())
            max_c = max(counts)
            min_c = min(counts)
            ratio = max_c / min_c if min_c > 0 else 0

            severity = "none"
            if len(surviving_docs) > 1:
                if ratio >= 10: severity = "critical"
                elif ratio >= 5: severity = "info"

            self.last_imbalance_info = SimpleNamespace(
                severity=severity,
                ratio=ratio,
                doc_distribution=dict(surviving_docs),
                max_chunks=max_c,
                min_chunks=min_c
            )
        else:
            self.last_imbalance_info = SimpleNamespace(
                severity="none", ratio=1.0, doc_distribution={}, max_chunks=0, min_chunks=0
            )
        # ---------------------------------------------------

        # --- v50.5: ESSENCE PARITY (Intelligente Essenz-Extraktion!) ---
        if chat_id and isinstance(chat_id, list) and len(chat_id) <= 10:
            logger.info(f"⚖️ ESSENCE PARITY aktiviert: {len(chat_id)} Dokumente")

            # Gruppiere Chunks nach Chat-ID
            docs_map = defaultdict(list)
            for res in top_results:
                cid = res.get('chat_id')
                docs_map[cid].append(res)

            # v50.5: MAX CHUNKS PRO DOKUMENT (Essenz-Extraktion!)
            max_chunks_per_doc = 12  # HYBRID-LÖSUNG: Begrenzung!

            logger.info(f"⚖️ Essenz-Extraktion: Max {max_chunks_per_doc} Chunks/Dokument (beste Auswahl!)")

            essence_results = []
            doc_metadata = []  # Für Prompt-Generierung

            for cid in chat_id:
                doc_chunks = docs_map.get(cid, [])

                # FALLBACK: Pre-Reranking
                if not doc_chunks:
                    logger.warning(f"  ⚠️ Dokument {cid[-8:]} hat 0 Chunks nach Reranking → Fallback.")
                    doc_chunks = [r for r in results if r.get('chat_id') == cid]

                # Sortiere nach Qualität (Hermeneutic Score = Relevanz!)
                doc_chunks_sorted = sorted(
                    doc_chunks, 
                    key=lambda x: x.get('hermeneutic_score', x.get('_final_score', 0)), 
                    reverse=True
                )

                # v50.5: Nimm die BESTEN N Chunks (Essenz!)
                selected = doc_chunks_sorted[:min(len(doc_chunks_sorted), max_chunks_per_doc)]
                essence_results.extend(selected)

                # Logging
                if selected:
                    doc_title = selected[0].get('metadata', {}).get('chat_title') or self._get_chat_title(cid)
                    avg_score = sum(c.get('hermeneutic_score', c.get('_final_score', 0)) for c in selected) / len(selected)

                    logger.info(f"  📄 {doc_title}: {len(doc_chunks)} verfügbar → {len(selected)} BESTE ausgewählt (Ø {avg_score:.2f})")

                    # v50.8 FIX: Ermittle repräsentatives Datum für das Dokument (für Sortierung im Prompt)
                    dates = [self.extract_date_from_metadata(c) for c in selected]
                    valid_dates = [d for d in dates if d != datetime.min]
                    rep_date = min(valid_dates) if valid_dates else datetime.min

                    # Speichere Metadaten für Prompt
                    doc_metadata.append({
                        'title': doc_title,
                        'chunks_available': len(doc_chunks),
                        'chunks_selected': len(selected),
                        'date': rep_date # WICHTIG für Prompt-Reihenfolge
                    })
                else:
                    doc_title = self._get_chat_title(cid)
                    logger.error(f"  ❌ {doc_title}: 0 Chunks verfügbar!")

                    doc_metadata.append({
                        'title': doc_title,
                        'chunks_available': 0,
                        'chunks_selected': 0,
                        'date': datetime.min
                    })

            # Ersetze top_results
            top_results = essence_results
            intent = "ESSENCE_PARITY"

            logger.info(f"✅ Essenz-Extraktion: {len(essence_results)} Chunks aus {len(chat_id)} Dokumenten")

        # --- NOTBREMSE ---
        if not top_results:
            return "Ich habe in den ausgewählten Dokumenten keine passenden Textstellen gefunden.", [], "NO_DATA"

        # NEU v50.6: CHRONOLOGISCHE SORTIERUNG
        # Sortiere Chunks nach Datum (wichtig für zeitliche Analysen!)
        top_results_sorted = sorted(top_results, key=self.extract_date_from_metadata)

        logger.info(f"📅 Chunks chronologisch sortiert: {len(top_results_sorted)} Stücke")

        # Debug-Log: Zeige Datums-Reihenfolge
        for i, res in enumerate(top_results_sorted[:5]):  # Erste 5
            date = self.extract_date_from_metadata(res)
            title = res.get('metadata', {}).get('chat_title', 'Unknown')
            logger.debug(f"  #{i+1}: {title} → {date.strftime('%d.%m.%Y') if date != datetime.min else 'o.D.'}")

        # v50.8 FIX: CHRONOLOGISCHE SORTIERUNG DER DOKUMENT-STRUKTUR
        # Wir sortieren doc_metadata ebenfalls nach Datum, damit die Prompt-Struktur stimmt!
        if doc_metadata:
            doc_metadata.sort(key=lambda x: x['date'])
            logger.info("📅 Dokument-Reihenfolge für Prompt chronologisch korrigiert.")

        # --- Context Building ---
        logger.info("📝 Baue Kontext zusammen...")

        sources_by_speaker = defaultdict(list)

        for i, res in enumerate(top_results_sorted):
            meta = res.get('metadata', {})

            if not meta:
                meta = {}
                res['metadata'] = meta

            speaker = meta.get('model_name') or meta.get('speaker') or meta.get('author') or 'Quelle'

            # Stelle sicher, dass chat_title vorhanden ist
            if 'chat_title' not in meta or not meta['chat_title']:
                chat_id_single = res.get('chat_id')
                if chat_id_single:
                    meta['chat_title'] = self._get_chat_title(chat_id_single)
                else:
                    meta['chat_title'] = 'Unknown'

            res['source_id'] = i + 1
            sources_by_speaker[speaker].append(res)

        context_text = ""

        for speaker, sources in sources_by_speaker.items():
            context_text += f"\n### {speaker.upper()}\n"

            for res in sources:
                sid = res['source_id']
                meta = res.get('metadata', {})
                title = meta.get('chat_title', 'Dokument')

                # v50.9 FIX: Datum explizit in den Header schreiben
                date_obj = self.extract_date_from_metadata(res)
                date_str = date_obj.strftime("%d.%m.%Y") if date_obj != datetime.min else "o.D."

                context_text += f"QUELLE [{sid}] ({title} | Datum: {date_str}):\n{res.get('content')}\n\n"

        # --- Finale Diagnostik ---
        final_doc_distribution = defaultdict(int)
        for res in top_results:
            chat_title = res.get('metadata', {}).get('chat_title', 'Unknown')
            final_doc_distribution[chat_title] += 1

        logger.info(f"📊 Finale Kontext-Verteilung ({len(top_results)} Chunks total):")
        for doc_title, count in sorted(final_doc_distribution.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(top_results)) * 100
            logger.info(f"  📄 {doc_title}: {count} Chunks ({percentage:.1f}%)")

        # --- v50.5: ESSENCE PARITY PROMPT ---
        base_instruction = ""
        mode_display = "UNKNOWN"

        if intent == "ESSENCE_PARITY":
            # Erstelle Struktur-Vorgabe (jetzt chronologisch sortiert!)
            structure_template = ""
            for i, doc_info in enumerate(doc_metadata):
                structure_template += f"\n### {i+1}. {doc_info['title']}\n"
                structure_template += f"[4-6 Sätze zur Frage mit EXAKT 3-4 Zitaten aus den {doc_info['chunks_selected']} verfügbaren Quellen]\n"

            base_instruction = f"""
**KRITISCHE REGEL - ESSENCE PARITY:**

Du hast aus {len(doc_metadata)} Texten die **essentiellsten Stellen** zur Frage erhalten.
Die Quellen sind CHRONOLOGISCH sortiert.

Die Quellenanzahl variiert ({min(d['chunks_selected'] for d in doc_metadata)} bis {max(d['chunks_selected'] for d in doc_metadata)} Quellen pro Text),
ABER: **Die Quellenanzahl reflektiert NUR die Original-Textlänge, NICHT die Wichtigkeit!**

**JEDER Text hat zur Frage GLEICH VIEL zu sagen!**

**SYNTHESE-VORGABE (PFLICHT):**
- EXAKT 1 Absatz pro Text (4-6 Sätze)
- EXAKT 3-4 Zitate pro Text (wähle die PRÄGNANTESTEN aus den verfügbaren!)
- GLEICHE Analyse-Tiefe (nicht oberflächlicher bei Texten mit weniger Quellen!)
- Halte dich STRIKT an diese Reihenfolge in der Analyse (Zeitverlauf):
{structure_template}

### VERGLEICHENDE SYNTHESE
[Vergleiche ALLE {len(doc_metadata)} Perspektiven zur Frage und ihre Entwicklung über die Zeit]

**QUALITÄTS-CHECK:**
- Sind alle {len(doc_metadata)} Abschnitte GLEICH LANG? (4-6 Sätze)
- Hat jeder 3-4 Zitate?
- Ist die Analyse-Tiefe überall gleich?
- Folgt die Analyse dem Zeitstrahl?
"""
            mode_display = "ESSENCE PARITY (Essenz-Extraktion + Erzwungene Gleichheit + Chronologie)"

        elif intent == "LITERARY":
            base_instruction = "Dies ist eine LITERARISCHE Analyse. Achte auf Nuancen, Stil und Metaphorik."
            mode_display = "LITERARY"
        elif intent == "FACTUAL":
            base_instruction = "Dies ist eine FAKTISCHE Recherche. Sei präzise und objektiv. Folge der Chronologie."
            mode_display = "FACTUAL"
        else:
            base_instruction = "Dies ist eine ANALYTISCHE Untersuchung. Vergleiche die Quellen systematisch."
            mode_display = "ANALYTICAL"

        logger.info(f"🧠 RAG Modus: {mode_display}")

        prompt = f"""
FRAGE: "{query}"

MODUS: {mode_display}

{base_instruction}

VERFÜGBARE QUELLEN (CHRONOLOGISCH SORTIERT):
{context_text}

AUFGABE:
Beantworte die Frage AUSSCHLIESSLICH basierend auf den oben genannten Quellen.

WICHTIGE REGELN:
1. **Quellen-Treue:** Nutze NUR die bereitgestellten Texte.
2. **Zitation:** Belege jede Aussage mit [Nummer].
3. **Vollständigkeit:** Alle Dokumente müssen in der Antwort vorkommen.
4. **Gleichberechtigung:** Gewichte NICHT nach Chunk-Anzahl!
5. **CHRONOLOGIE:** Die Quellen sind nach Datum sortiert. Deine Antwort MUSS diese zeitliche Entwicklung abbilden (von alt nach neu).

ANTWORT:
"""

        # --- Generation ---
        logger.info("📤 Sende Prompt an LLM...")

        max_retries = 3

        for attempt in range(max_retries):
            try:
                model = genai.GenerativeModel(
                    model_name=MODEL_SYNTHESIS,
                    system_instruction="Du bist ein präziser Forschungs-Assistent, der alle bereitgestellten Quellen strikt gleichberechtigt behandelt und Essenz über Quantität stellt."
                )

                response = model.generate_content(prompt)

                if not response.parts:
                    logger.error(f"❌ Modell verweigert Antwort. Feedback: {response.prompt_feedback}")
                    return "⚠️ Das Modell konnte keine Antwort generieren (Sicherheitsfilter).", top_results_sorted, intent

                final_text = self.clean_citation_format(response.text)

                logger.info("✅ Antwort empfangen!")

                return final_text, top_results_sorted, intent

            except Exception as e:
                logger.error(f"⚠️ API Versuch {attempt+1} fehlgeschlagen: {e}")

                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 2)
                    continue

                return f"❌ API-Limit oder Fehler: {e}", top_results_sorted, intent

        return "❌ API nicht verfügbar.", top_results_sorted, intent

    def split_thought_and_speech(self, text: str) -> Tuple[str, str]:
        """Trennt Thinking-Blocks."""
        if not text:
            return "", ""

        pattern = r'(> \*\*Thinking:\*\*.*?)(\n\n|$)(.*)'
        match = re.search(pattern, text, re.DOTALL)

        if match:
            return match.group(1).strip(), match.group(3).strip()

        return "", text

    def validate_citations(self, answer: str, num_sources: int) -> List[str]:
        """Struktureller Citation-Check."""
        warnings = []

        matches = re.findall(r'\[(\d+)\]', answer)

        if not matches:
            warnings.append("⚠️ Warnung: Keine Zitationen gefunden.")
            return warnings

        for m in matches:
            idx = int(m)
            if idx < 1 or idx > num_sources:
                warnings.append(f"⚠️ Ungültige Zitation: [{idx}]")

        return warnings

    def verify_fact_match(self, claim: str, source_text: str, source_meta: Dict) -> Tuple[bool, str]:
        """Tiefenprüfung via Enforcer (FIXED v50.8)."""
        try:
            from modules.hermeneutic_enforcer import HermeneuticEnforcer

            enforcer = HermeneuticEnforcer()
            sources = [{"content": source_text, "metadata": source_meta}]

            # FIX: Robustes Unpacking, da Enforcer manchmal 2 oder 3 Werte liefert
            result = enforcer.validate_claim(claim=claim, sources=sources)

            if isinstance(result, tuple):
                if len(result) == 3:
                    is_valid, classification, reason = result
                    return is_valid, f"[{classification.upper()}] {reason}"
                elif len(result) == 2:
                    is_valid, reason = result
                    return is_valid, reason

            # Fallback
            return True, "Enforcer Format Unknown"

        except Exception as e:
            logger.error(f"Enforcer Error: {e}")
            return True, f"ENFORCER ERROR: {e}"

    async def verify_facts_parallel(
        self, 
        sentences: List[str], 
        results: List[Dict], 
        progress_callback=None
    ) -> List[Dict]:
        """Parallele Faktenprüfung."""
        sem = asyncio.Semaphore(5)
        completed = 0
        total = len(sentences)

        async def _bounded_check(sent):
            nonlocal completed

            async with sem:
                loop = asyncio.get_running_loop()

                matches = re.findall(r'\[(\d+)\]', sent)
                if not matches:
                    return None

                results_for_sentence = []

                for m in matches:
                    idx = int(m) - 1

                    if 0 <= idx < len(results):
                        source_content = results[idx].get('content', '')
                        source_meta = results[idx].get('metadata', {})

                        is_valid, reason = await loop.run_in_executor(
                            None,
                            partial(self.verify_fact_match, sent, source_content, source_meta)
                        )

                        results_for_sentence.append({
                            'sentence': sent,
                            'source_id': m,
                            'valid': is_valid,
                            'reason': reason
                        })

                completed += 1

                if progress_callback:
                    progress_callback(completed / total)

                return results_for_sentence

        tasks = [_bounded_check(sent) for sent in sentences]
        all_results = await asyncio.gather(*tasks)

        flat_log = []
        for res_list in all_results:
            if res_list:
                flat_log.extend(res_list)

        return flat_log