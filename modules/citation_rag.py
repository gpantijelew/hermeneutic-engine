# modules/citation_rag.py - v50.5: ESSENCE PARITY (Intelligente Essenz-Extraktion)
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
    
    def generate_answer(
        self, 
        query: str, 
        results: List[Dict],
        strict_parity: bool = False
    ) -> Tuple[str, List[Dict], str]:
        """
        v50.5: ESSENCE PARITY - Intelligente Essenz-Extraktion.
        
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
                    
                    # Speichere Metadaten für Prompt
                    doc_metadata.append({
                        'title': doc_title,
                        'chunks_available': len(doc_chunks),
                        'chunks_selected': len(selected)
                    })
                else:
                    doc_title = self._get_chat_title(cid)
                    logger.error(f"  ❌ {doc_title}: 0 Chunks verfügbar!")
                    
                    doc_metadata.append({
                        'title': doc_title,
                        'chunks_available': 0,
                        'chunks_selected': 0
                    })
            
            # Ersetze top_results
            top_results = essence_results
            intent = "ESSENCE_PARITY"
            
            logger.info(f"✅ Essenz-Extraktion: {len(essence_results)} Chunks aus {len(chat_id)} Dokumenten")
        
        # --- NOTBREMSE ---
        if not top_results:
            return "Ich habe in den ausgewählten Dokumenten keine passenden Textstellen gefunden.", [], "NO_DATA"
        
        # --- Context Building ---
        logger.info("📝 Baue Kontext zusammen...")
        
        sources_by_speaker = defaultdict(list)
        
        for i, res in enumerate(top_results):
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
                
                context_text += f"QUELLE [{sid}] ({title}):\n{res.get('content')}\n\n"
        
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
            # Erstelle Struktur-Vorgabe
            structure_template = ""
            for i, doc_info in enumerate(doc_metadata):
                structure_template += f"\n### {i+1}. {doc_info['title']}\n"
                structure_template += f"[4-6 Sätze zur Frage mit EXAKT 3-4 Zitaten aus den {doc_info['chunks_selected']} verfügbaren Quellen]\n"
            
            base_instruction = f"""
**KRITISCHE REGEL - ESSENCE PARITY:**

Du hast aus {len(doc_metadata)} Texten die **essentiellsten Stellen** zur Frage erhalten.

Die Quellenanzahl variiert ({min(d['chunks_selected'] for d in doc_metadata)} bis {max(d['chunks_selected'] for d in doc_metadata)} Quellen pro Text),
ABER: **Die Quellenanzahl reflektiert NUR die Original-Textlänge, NICHT die Wichtigkeit!**

**JEDER Text hat zur Frage GLEICH VIEL zu sagen!**

**SYNTHESE-VORGABE (PFLICHT):**
- EXAKT 1 Absatz pro Text (4-6 Sätze)
- EXAKT 3-4 Zitate pro Text (wähle die PRÄGNANTESTEN aus den verfügbaren!)
- GLEICHE Analyse-Tiefe (nicht oberflächlicher bei Texten mit weniger Quellen!)

**STRUKTUR (PFLICHT):**
{structure_template}

### VERGLEICHENDE SYNTHESE
[Vergleiche ALLE {len(doc_metadata)} Perspektiven zur Frage]

**QUALITÄTS-CHECK:**
- Sind alle {len(doc_metadata)} Abschnitte GLEICH LANG? (4-6 Sätze)
- Hat jeder 3-4 Zitate?
- Ist die Analyse-Tiefe überall gleich?
"""
            mode_display = "ESSENCE PARITY (Essenz-Extraktion + Erzwungene Gleichheit)"
        
        elif intent == "LITERARY":
            base_instruction = "Dies ist eine LITERARISCHE Analyse. Achte auf Nuancen, Stil und Metaphorik."
            mode_display = "LITERARY"
        elif intent == "FACTUAL":
            base_instruction = "Dies ist eine FAKTISCHE Recherche. Sei präzise und objektiv."
            mode_display = "FACTUAL"
        else:
            base_instruction = "Dies ist eine ANALYTISCHE Untersuchung. Vergleiche die Quellen systematisch."
            mode_display = "ANALYTICAL"
        
        logger.info(f"🧠 RAG Modus: {mode_display}")
        
        prompt = f"""
FRAGE: "{query}"

MODUS: {mode_display}

{base_instruction}

VERFÜGBARE QUELLEN:
{context_text}

AUFGABE:
Beantworte die Frage AUSSCHLIESSLICH basierend auf den oben genannten Quellen.

WICHTIGE REGELN:
1. **Quellen-Treue:** Nutze NUR die bereitgestellten Texte.
2. **Zitation:** Belege jede Aussage mit [Nummer].
3. **Vollständigkeit:** Alle Dokumente müssen in der Antwort vorkommen.
4. **Gleichberechtigung:** Gewichte NICHT nach Chunk-Anzahl!

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
                    return "⚠️ Das Modell konnte keine Antwort generieren (Sicherheitsfilter).", top_results, intent
                
                final_text = self.clean_citation_format(response.text)
                
                logger.info("✅ Antwort empfangen!")
                
                return final_text, top_results, intent
                
            except Exception as e:
                logger.error(f"⚠️ API Versuch {attempt+1} fehlgeschlagen: {e}")
                
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 2)
                    continue
                
                return f"❌ API-Limit oder Fehler: {e}", top_results, intent
        
        return "❌ API nicht verfügbar.", top_results, intent
    
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
        """Tiefenprüfung via Enforcer."""
        try:
            from modules.hermeneutic_enforcer import HermeneuticEnforcer
            
            enforcer = HermeneuticEnforcer()
            sources = [{"content": source_text, "metadata": source_meta}]
            
            is_valid, classification, reason = enforcer.validate_claim(claim=claim, sources=sources)
            
            return is_valid, f"[{classification.upper()}] {reason}"
            
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