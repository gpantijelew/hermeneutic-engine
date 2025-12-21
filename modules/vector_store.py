# modules/vector_store.py
import os
import logging
import time
import uuid
import re
from typing import List, Dict, Optional, Any, Tuple
import google.generativeai as genai
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

# --- NEU (v49): BM25 für RRF ---
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logging.warning("⚠️ rank-bm25 nicht installiert. RRF läuft im Fallback-Modus.")

# Globaler Cache für den BM25 Index (verhindert Rebuild bei jedem Request)
_BM25_INDEX = None
_BM25_DOC_MAP = None # Mapping von Index-ID zu Firestore-Dokumenten
_BM25_LAST_UPDATE = 0
# -------------------------------

# --- Pre-Processing Import ---
try:
    from modules.preprocessing.chunk_classifier import ChunkClassifier
except ImportError:
    ChunkClassifier = None
    logging.warning("⚠️ ChunkClassifier konnte nicht importiert werden. Pre-Processing inaktiv.")

# --- Metadata Extractors ---
from modules.utils.date_extractor import extract_date_from_chat_title
from modules.utils.version_extractor import extract_version_from_chat_title
# --------------------------------

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguration
EMBEDDING_MODEL = "models/text-embedding-004"
DIMENSIONS = 768
COLLECTION_NAME = "embeddings"
RRF_K = 60  # Standard-Konstante für RRF Fusion

# API Key Setup
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
                    task_type="retrieval_document",
                    title=None
                )
                return result['embedding']
            except Exception as e:
                error_msg = str(e)
                wait_time = (attempt + 1) * 5
                if "429" in error_msg or "Resource exhausted" in error_msg:
                    logger.warning(f"⏳ Rate Limit bei Embedding. Warte {wait_time}s... (Versuch {attempt+1}/{retries})")
                else:
                    logger.warning(f"⚠️ Embedding Fehler: {e}")
                time.sleep(wait_time)
        return None

    def chunk_text(self, text: str, max_tokens: int = 1000, overlap: int = 300) -> List[str]:
        if not text: return []

        chunk_size_chars = max_tokens * 4
        overlap_chars = overlap * 4

        speaker_pattern = re.compile(r"(?:\*\*|#)?\s*Modell:?\s*(.*?)(?:\*\*|$|\n)", re.IGNORECASE)
        speaker_matches = list(speaker_pattern.finditer(text))

        if len(text) <= chunk_size_chars: return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size_chars
            if end < len(text):
                last_period = text.rfind('.', start, end)
                if last_period != -1 and last_period > start + (chunk_size_chars // 2):
                    end = last_period + 1

            raw_chunk = text[start:end]

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

        # Cache invalidieren, da sich Daten ändern
        global _BM25_INDEX
        _BM25_INDEX = None 

        self.delete_chat_embeddings(chat_id)

        batch = self.db.batch()
        operation_count = 0
        total_chunks = 0
        skipped_count = 0

        if custom_metadata is None: custom_metadata = {}

        classifier = ChunkClassifier() if ChunkClassifier else None

        for msg in messages:
            content = msg.get('content', '')
            role = msg.get('role') or msg.get('author') or 'unknown'
            msg_id = msg.get('id', str(uuid.uuid4()))

            if not content or len(content.strip()) < 70:
                skipped_count += 1
                continue

            chunks = self.chunk_text(content)

            for i, chunk_text in enumerate(chunks):
                vector_values = self._get_embedding(chunk_text)
                if not vector_values: continue

                doc_id = f"{chat_id}_{msg_id}_{i}"
                doc_ref = self.db.collection(COLLECTION_NAME).document(doc_id)

                meta = {"role": role, "source_length": len(content)}
                meta.update(custom_metadata)

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
                    "embedding": Vector(vector_values),
                    "metadata": meta,
                    "created_at": firestore.SERVER_TIMESTAMP
                }

                batch.set(doc_ref, data)
                operation_count += 1
                total_chunks += 1

                if operation_count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    operation_count = 0
                    time.sleep(0.5)

        if operation_count > 0: batch.commit()

        logger.info(f"✅ Chat {chat_id}: {total_chunks} Chunks.")
        return total_chunks, skipped_count

    def delete_chat_embeddings(self, chat_id: str):
        docs = self.db.collection(COLLECTION_NAME).where("chat_id", "==", chat_id).stream()
        for doc in docs: doc.reference.delete()

        # Cache invalidieren
        global _BM25_INDEX
        _BM25_INDEX = None

    # --- v49: BM25 INDEX BUILDER ---
    def _ensure_bm25_index(self):
        """
        Baut den BM25 Index im Speicher auf, falls er noch nicht existiert.
        Holt nur 'content' und 'metadata' aus Firestore (effizient).
        """
        global _BM25_INDEX, _BM25_DOC_MAP

        if _BM25_INDEX is not None:
            return # Index ist bereits heiß

        if not BM25_AVAILABLE:
            return

        logger.info("🏗️ Baue BM25 Index auf (Initial Load)...")
        start_time = time.time()

        # Projektion: Wir laden nur content und metadata, keine Vektoren (spart Bandbreite)
        docs = self.db.collection(COLLECTION_NAME).select(['content', 'metadata', 'chat_id']).stream()

        corpus = []
        doc_map = {}

        count = 0
        for doc in docs:
            data = doc.to_dict()
            content = data.get('content', "")

            # Einfacher Tokenizer (lowercase + split)
            # Für v50 könnte man hier Spacy/NLTK nutzen
            tokens = content.lower().split()
            corpus.append(tokens)

            # Wir speichern das ganze Doc-Objekt im RAM-Cache für schnellen Zugriff
            # Das vermeidet einen zweiten DB-Call beim Retrieval
            data['vector_doc_id'] = doc.id
            doc_map[count] = data
            count += 1

        if corpus:
            _BM25_INDEX = BM25Okapi(corpus)
            _BM25_DOC_MAP = doc_map
            logger.info(f"✅ BM25 Index gebaut: {count} Dokumente in {time.time() - start_time:.2f}s")
        else:
            logger.warning("⚠️ Keine Dokumente für BM25 gefunden.")

    def _tokenize(self, text: str) -> List[str]:
        return text.lower().split()

    def semantic_search(self, query: str, limit: int = 10, filter_role: str = None, allowed_chat_ids: List[str] = None) -> Tuple[List[Dict], List[float]]:
        query_vector = self._get_embedding(query)
        if not query_vector: return [], None

        collection_ref = self.db.collection(COLLECTION_NAME)
        raw_limit = limit * 20 if (filter_role or allowed_chat_ids) else limit * 2
        fetch_limit = min(raw_limit, 1000)

        print(f"🔍 Vektor-Suche: Hole {fetch_limit} Kandidaten aus DB...")

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
            if allowed_chat_ids is not None and data.get('chat_id') not in allowed_chat_ids: continue

            meta = data.get('metadata', {})

            # On-the-fly Metadaten-Reparatur
            if 'chat_title' in meta:
                changed = False
                if not meta.get('date'):
                    meta['date'] = extract_date_from_chat_title(meta['chat_title'])
                    changed = True
                if not meta.get('version'):
                    spk = meta.get('model_name') or meta.get('speaker') or meta.get('role')
                    meta['version'] = extract_version_from_chat_title(meta['chat_title'], spk)
                    changed = True
                if changed: data['metadata'] = meta

            # --- FIX: Intelligenter Rollen-Filter ---
            role = meta.get('role', 'unknown').lower()

            if filter_role:
                f_role = filter_role.lower()

                # Mapping für Synonyme
                is_model_search = f_role in ["model", "assistant", "ai", "ki"]
                is_model_content = role in ["model", "assistant", "ai", "ki"]

                # Wenn nach Model gesucht wird, akzeptieren wir alle Model-Varianten
                if is_model_search and is_model_content:
                    pass # Match!
                # Sonst strikter Vergleich
                elif f_role != role:
                    continue
            # ----------------------------------------
            if 'embedding' in data:
                vec_obj = data['embedding']
                try:
                    data['embedding_vector'] = list(vec_obj)
                except:
                    data['embedding_vector'] = vec_obj

            data['vector_doc_id'] = doc.id

            # Score normalisieren (Firestore gibt Distance, wir wollen Similarity?)
            # Firestore Cosine Distance: 0 = gleich, 2 = gegenteil.
            # Wir konvertieren nicht explizit, da RRF nur den RANK braucht.

            cleaned_results.append(data)
            if len(cleaned_results) >= limit * 3: break

        print(f"✅ Vektor-Suche: {len(cleaned_results)} Treffer.")
        return cleaned_results, query_vector

    # --- v49: RRF HYBRID SEARCH ---
    def hybrid_search_rrf(self, query: str, limit: int = 10, filter_role: str = None, allowed_chat_ids: List[str] = None) -> Tuple[List[Dict], Any]:
        """
        Führt eine echte Hybrid-Suche durch:
        1. Vektor-Suche (Semantic)
        2. BM25-Suche (Keyword)
        3. Reciprocal Rank Fusion (RRF)
        """
        # 1. Vektor-Suche (Hole mehr Kandidaten für bessere Fusion)
        vector_candidates, query_vector = self.semantic_search(
            query, limit=limit * 3, filter_role=filter_role, allowed_chat_ids=allowed_chat_ids
        )

        if not BM25_AVAILABLE:
            # Fallback auf alte Methode, wenn Library fehlt
            return vector_candidates[:limit], query_vector

        # 2. BM25 Suche
        self._ensure_bm25_index()

        bm25_candidates = []
        if _BM25_INDEX:
            tokenized_query = self._tokenize(query)
            # Hole Scores für ALLE Dokumente im Index
            scores = _BM25_INDEX.get_scores(tokenized_query)
            # Hole Top N Indizes
            top_n = _BM25_INDEX.get_top_n(tokenized_query, list(_BM25_DOC_MAP.keys()), n=limit * 3)

            for idx in top_n:
                doc_data = _BM25_DOC_MAP[idx]
                # Filter anwenden (muss auch hier passieren!)
                if allowed_chat_ids and doc_data.get('chat_id') not in allowed_chat_ids:
                    continue

                role = doc_data.get('metadata', {}).get('role', 'unknown')
                if filter_role and filter_role.lower() != role.lower():
                    continue

                bm25_candidates.append(doc_data)

        print(f"📚 BM25-Suche: {len(bm25_candidates)} Treffer.")

        # 3. RRF Fusion
        # Wir bauen ein Dictionary: doc_id -> RRF Score
        rrf_scores = {}

        # Helper für RRF Formel: score = 1 / (k + rank)
        def add_scores(candidates, weight=1.0):
            for rank, doc in enumerate(candidates):
                doc_id = doc.get('vector_doc_id')
                if not doc_id: continue

                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = {"doc": doc, "score": 0.0}

                rrf_scores[doc_id]["score"] += weight * (1 / (RRF_K + rank + 1))

        add_scores(vector_candidates)
        add_scores(bm25_candidates)

        # Sortieren nach RRF Score
        sorted_results = sorted(rrf_scores.values(), key=lambda x: x['score'], reverse=True)

        # Top N extrahieren
        final_results = [item['doc'] for item in sorted_results[:limit]]

        # Debug Info hinzufügen
        for res in final_results:
            res['_rrf_active'] = True

        print(f"⚖️ RRF Fusion: {len(final_results)} finale Treffer.")
        return final_results, query_vector

    # Legacy Wrapper für Kompatibilität
    def hybrid_search(self, query: str, keywords: List[str] = None, limit: int = 10, filter_role: str = None, allowed_chat_ids: List[str] = None, keyword_weight: float = 0.3) -> Tuple[List[Dict], Any]:
        """
        Legacy Methode. Leitet jetzt auf RRF um, ignoriert aber 'keywords' Liste,
        da BM25 die Keywords selbst aus der Query extrahiert.
        """
        return self.hybrid_search_rrf(query, limit, filter_role, allowed_chat_ids)