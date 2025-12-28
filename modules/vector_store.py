import os
import logging
import time
import uuid
import re
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
import google.generativeai as genai
from modules.config import EMBEDDING_MODEL, EMBEDDING_DIMENSIONS
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

# --- BM25 für RRF ---
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logging.warning("⚠️ rank-bm25 nicht installiert. RRF läuft im Fallback-Modus.")

# Globaler Cache für BM25
_BM25_INDEX = None
_BM25_DOC_MAP = None
_BM25_LAST_UPDATE = 0

# --- Pre-Processing Import ---
try:
    from modules.preprocessing.chunk_classifier import ChunkClassifier
except ImportError:
    ChunkClassifier = None

# --- Metadata Extractors ---
from modules.utils.date_extractor import extract_date_from_chat_title
from modules.utils.version_extractor import extract_version_from_chat_title

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguration
EMBEDDING_MODEL = "models/text-embedding-004"
COLLECTION_NAME = "embeddings"
RRF_K = 60

# API Key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class FirestoreVectorStore:
    def __init__(self, db_client: firestore.Client):
        self.db = db_client

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        if not text or not text.strip():
            return None

        retries = 3
        for attempt in range(retries):
            try:
                result = genai.embed_content(
                    model=EMBEDDING_MODEL,
                    content=text,
                    task_type="retrieval_document"
                )
                return result['embedding']
            except Exception as e:
                time.sleep((attempt + 1) * 2)

        return None

    def chunk_text(self, text: str, max_tokens: int = 1000, overlap: int = 300) -> List[str]:
        if not text:
            return []

        chunk_size_chars = max_tokens * 4
        overlap_chars = overlap * 4

        # Speaker Detection für Kontext
        speaker_pattern = re.compile(r"(?:\*\*|#)?\s*Modell:?\s*(.*?)(?:\*\*|$|\n)", re.IGNORECASE)
        speaker_matches = list(speaker_pattern.finditer(text))

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size_chars

            if end < len(text):
                last_period = text.rfind('.', start, end)
                if last_period != -1 and last_period > start + (chunk_size_chars // 2):
                    end = last_period + 1

            raw_chunk = text[start:end]

            # Kontext-Injektion
            current_speaker = None
            for m in speaker_matches:
                if m.start() < end:
                    current_speaker = m.group(1).strip()

            final_chunk = raw_chunk
            if current_speaker and f"Modell: {current_speaker}" not in raw_chunk[:50]:
                final_chunk = f"[Kontext: Sprecher ist {current_speaker}] {raw_chunk}"

            chunks.append(final_chunk)
            start = end - overlap_chars

        return chunks

    def process_and_store_chat(self, chat_id: str, messages: List[Dict], custom_metadata: Dict = None):
        logger.info(f"🔄 Starte Vektorisierung für Chat {chat_id}...")

        global _BM25_INDEX
        _BM25_INDEX = None

        self.delete_chat_embeddings(chat_id)

        batch = self.db.batch()
        op_count = 0
        total_chunks = 0

        if custom_metadata is None:
            custom_metadata = {}

        classifier = ChunkClassifier() if ChunkClassifier else None

        for msg in messages:
            content = msg.get('content', '')
            role = msg.get('role') or msg.get('author') or 'unknown'
            msg_id = msg.get('id', str(uuid.uuid4()))

            if not content or len(content.strip()) < 50:
                continue

            chunks = self.chunk_text(content)

            for i, chunk_text in enumerate(chunks):
                vec = self._get_embedding(chunk_text)
                if not vec:
                    continue

                doc_id = f"{chat_id}_{msg_id}_{i}"
                doc_ref = self.db.collection(COLLECTION_NAME).document(doc_id)

                meta = {"role": role, "source_length": len(content)}
                meta.update(custom_metadata)

                # Metadata Extraction
                chat_title = meta.get('chat_title', '')
                speaker_hint = meta.get('speaker') or meta.get('model') or role

                if chat_title:
                    if 'date' not in meta or not meta['date']:
                        meta['date'] = extract_date_from_chat_title(chat_title)

                    if 'version' not in meta or not meta['version']:
                        meta['version'] = extract_version_from_chat_title(chat_title, speaker_hint)

                if classifier:
                    meta = classifier.process_chunk(chunk_text, meta)

                data = {
                    "chat_id": chat_id,
                    "message_id": msg_id,
                    "chunk_index": i,
                    "content": chunk_text,
                    "embedding": Vector(vec),
                    "metadata": meta,
                    "created_at": firestore.SERVER_TIMESTAMP
                }

                batch.set(doc_ref, data)
                op_count += 1
                total_chunks += 1

                if op_count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    op_count = 0
                    time.sleep(0.5)

        if op_count > 0:
            batch.commit()

        logger.info(f"✅ Chat {chat_id}: {total_chunks} Chunks gespeichert.")
        return total_chunks, 0

    def delete_chat_embeddings(self, chat_id: str):
        docs = self.db.collection(COLLECTION_NAME).where("chat_id", "==", chat_id).stream()
        for doc in docs:
            doc.reference.delete()

        global _BM25_INDEX
        _BM25_INDEX = None

    def _ensure_bm25_index(self):
        global _BM25_INDEX, _BM25_DOC_MAP

        if _BM25_INDEX is not None:
            return

        if not BM25_AVAILABLE:
            return

        logger.info("🏗️ Baue BM25 Index auf...")
        start = time.time()

        docs = self.db.collection(COLLECTION_NAME).select(['content', 'metadata', 'chat_id']).stream()

        corpus = []
        doc_map = {}
        count = 0

        for doc in docs:
            d = doc.to_dict()
            d['vector_doc_id'] = doc.id
            corpus.append(d.get('content', '').lower().split())
            doc_map[count] = d
            count += 1

        if corpus:
            _BM25_INDEX = BM25Okapi(corpus)
            _BM25_DOC_MAP = doc_map
            elapsed = time.time() - start
            logger.info(f"✅ BM25 Index gebaut: {count} Dokumente in {elapsed:.2f}s")

    def _cosine_similarity(self, vec_a, vec_b):
        """Berechnet Cosine Similarity zwischen zwei Numpy Arrays."""
        return np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))

    def _get_chat_title(self, chat_id: str) -> str:
        try:
            chat_doc = self.db.collection('chats').document(chat_id).get()
            if chat_doc.exists:
                return chat_doc.to_dict().get('title', f'Doc {chat_id[-8:]}')
            else:
                return f'Doc {chat_id[-8:]}'
        except Exception as e:
            logger.warning(f"⚠️ Konnte Titel für {chat_id[-8:]} nicht laden: {e}")
            return f'Doc {chat_id[-8:]}'

    def semantic_search(
        self, 
        query: str, 
        limit: int = 10, 
        filter_role: str = None, 
        allowed_chat_ids: List[str] = None
    ) -> Tuple[List[Dict], List[float]]:
        """
        v50.2: Investigativ-Modus mit Fairness-Quota + Titel-Transparenz.
        """
        query_vector = self._get_embedding(query)
        if not query_vector:
            return [], None

        # --- v50.2: INVESTIGATIVE MODE MIT FAIRNESS-QUOTA ---
        if allowed_chat_ids and len(allowed_chat_ids) <= 5:
            logger.info(f"🕵️‍♂️ Investigativ-Modus mit Fairness-Quota: {len(allowed_chat_ids)} Dokumente...")

            docs_by_chat = {cid: [] for cid in allowed_chat_ids}

            docs = self.db.collection(COLLECTION_NAME).where("chat_id", "in", allowed_chat_ids).stream()
            q_vec_np = np.array(query_vector)

            for doc in docs:
                data = doc.to_dict()

                if filter_role and filter_role.lower() not in data.get('metadata', {}).get('role', '').lower():
                    continue

                vec_obj = data.get('embedding')
                if not vec_obj:
                    continue

                try:
                    vec = np.array(list(vec_obj))
                except:
                    vec = np.array(vec_obj)

                score = self._cosine_similarity(q_vec_np, vec)
                data['vector_doc_id'] = doc.id
                data['score'] = float(score)

                cid = data.get('chat_id')
                if cid in docs_by_chat:
                    docs_by_chat[cid].append(data)

            # FAIRNESS-QUOTA
            quota_per_doc = max(20, (limit * 2) // len(allowed_chat_ids))
            logger.info(f"⚖️ Fairness-Quota: {quota_per_doc} Chunks pro Dokument")

            fair_candidates = []

            for cid, chunks in docs_by_chat.items():
                if not chunks:
                    chat_title = self._get_chat_title(cid)
                    logger.warning(f"  ⚠️ {chat_title}: Keine Chunks gefunden (Filter zu strikt?)")
                    continue

                chunks.sort(key=lambda x: x['score'], reverse=True)

                selected_count = min(len(chunks), quota_per_doc)
                fair_candidates.extend(chunks[:selected_count])

                chat_title = self._get_chat_title(cid)
                avg_score = sum(c['score'] for c in chunks[:selected_count]) / selected_count
                logger.info(f"  📄 {chat_title}: {len(chunks)} total → {selected_count} selected (Ø Score: {avg_score:.2f})")

            fair_candidates.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"✅ Fairness-Quota angewendet: {len(fair_candidates)} Chunks aus {len(allowed_chat_ids)} Dokumenten")

            return fair_candidates[:limit * 2], query_vector

        # --- STANDARD: GLOBALE SUCHE ---
        else:
            collection_ref = self.db.collection(COLLECTION_NAME)
            fetch_limit = 1000

            vector_query = collection_ref.find_nearest(
                vector_field="embedding",
                query_vector=Vector(query_vector),
                distance_measure=DistanceMeasure.COSINE,
                limit=fetch_limit
            )

            results = vector_query.get()
            cleaned_results = []

            for doc in results:
                data = doc.to_dict()

                if allowed_chat_ids and data.get('chat_id') not in allowed_chat_ids:
                    continue

                if filter_role and filter_role.lower() not in data.get('metadata', {}).get('role', '').lower():
                    continue

                meta = data.get('metadata', {})
                if 'chat_title' in meta:
                    changed = False
                    if not meta.get('date'):
                        meta['date'] = extract_date_from_chat_title(meta['chat_title'])
                        changed = True
                    if not meta.get('version'):
                        spk = meta.get('model_name') or meta.get('speaker') or meta.get('role')
                        meta['version'] = extract_version_from_chat_title(meta['chat_title'], spk)
                        changed = True
                    if changed:
                        data['metadata'] = meta

                data['vector_doc_id'] = doc.id
                cleaned_results.append(data)

                if len(cleaned_results) >= limit * 2:
                    break

            return cleaned_results, query_vector

    def hybrid_search_rrf(
        self, 
        query: str, 
        limit: int = 10, 
        filter_role: str = None, 
        allowed_chat_ids: List[str] = None
    ) -> Tuple[List[Dict], Any]:
        """
        v50.3: RRF mit VIP-Schutz (Verhindert das Abschneiden ausgewählter Dokumente).
        """
        # 1. Vektor-Suche
        vector_candidates, query_vector = self.semantic_search(
            query, 
            limit=limit * 3, 
            filter_role=filter_role, 
            allowed_chat_ids=allowed_chat_ids
        )

        if not BM25_AVAILABLE:
            logger.info("📚 BM25-Suche: 0 Treffer (Library nicht verfügbar).")
            return vector_candidates[:limit], query_vector

        # 2. BM25 Suche
        self._ensure_bm25_index()
        bm25_candidates = []

        if _BM25_INDEX:
            tokenized_query = query.lower().split()
            top_n_indices = _BM25_INDEX.get_top_n(tokenized_query, list(_BM25_DOC_MAP.keys()), n=2000)

            for idx in top_n_indices:
                doc_data = _BM25_DOC_MAP[idx]

                if allowed_chat_ids and doc_data.get('chat_id') not in allowed_chat_ids:
                    continue

                if filter_role and filter_role.lower() not in doc_data.get('metadata', {}).get('role', '').lower():
                    continue

                bm25_candidates.append(doc_data)
                if len(bm25_candidates) >= limit * 3:
                    break

            logger.info(f"📚 BM25-Suche: {len(bm25_candidates)} Treffer.")

        # 3. RRF Fusion
        rrf_scores = {}

        def add_scores(candidates, weight=1.0):
            for rank, doc in enumerate(candidates):
                doc_id = doc.get('vector_doc_id')
                if not doc_id: continue

                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = {"doc": doc, "score": 0.0}

                rrf_scores[doc_id]["score"] += weight * (1 / (RRF_K + rank + 1))

        add_scores(vector_candidates)
        add_scores(bm25_candidates)

        sorted_results = sorted(rrf_scores.values(), key=lambda x: x['score'], reverse=True)

        # --- VIP-SCHUTZ (NEU!) ---
        # Wir schneiden nicht einfach bei 'limit' ab.
        # Wir stellen sicher, dass JEDES ausgewählte Dokument (allowed_chat_ids)
        # mit mindestens 3 Chunks vertreten ist, bevor wir den Rest auffüllen.

        final_results = []

        if allowed_chat_ids and len(allowed_chat_ids) <= 10:
            # Gruppiere alle verfügbaren Ergebnisse nach Chat-ID
            results_by_chat = {cid: [] for cid in allowed_chat_ids}
            for item in sorted_results:
                doc = item['doc']
                cid = doc.get('chat_id')
                if cid in results_by_chat:
                    results_by_chat[cid].append(doc)

            # 1. VIP-Runde: Nimm die Top 3 von JEDEM Dokument (egal wie schlecht der Score ist)
            vip_set = set() # Um Duplikate zu vermeiden
            for cid, docs in results_by_chat.items():
                top_3 = docs[:3]
                for d in top_3:
                    # Wir nutzen vector_doc_id als Unique Key
                    uid = d.get('vector_doc_id')
                    if uid not in vip_set:
                        final_results.append(d)
                        vip_set.add(uid)

            logger.info(f"🛡️ VIP-Schutz: {len(final_results)} Chunks garantiert aufgenommen.")

            # 2. Auffüllen: Nimm den Rest streng nach Score, bis Limit erreicht
            for item in sorted_results:
                doc = item['doc']
                uid = doc.get('vector_doc_id')

                if len(final_results) >= limit:
                    break

                if uid not in vip_set:
                    final_results.append(doc)
                    vip_set.add(uid)

        else:
            # Standard-Verhalten (ohne VIP-Schutz)
            final_results = [item['doc'] for item in sorted_results[:limit]]

        for res in final_results:
            res['_rrf_active'] = True

        logger.info(f"⚖️ RRF Fusion: {len(final_results)} finale Treffer.")

        return final_results, query_vector

    # Legacy Wrapper
    def hybrid_search(self, query: str, keywords: List[str] = None, limit: int = 10, filter_role: str = None, allowed_chat_ids: List[str] = None, keyword_weight: float = 0.3) -> Tuple[List[Dict], Any]:
        return self.hybrid_search_rrf(query, limit, filter_role, allowed_chat_ids)