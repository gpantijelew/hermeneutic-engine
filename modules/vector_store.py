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

# --- NEU: Pre-Processing Import ---
# Falls das Modul noch nicht existiert, fangen wir den Fehler ab, 
# damit die App nicht crasht, bevor du die Datei erstellt hast.
try:
    from modules.preprocessing.chunk_classifier import ChunkClassifier
except ImportError:
    ChunkClassifier = None
    logging.warning("⚠️ ChunkClassifier konnte nicht importiert werden. Pre-Processing inaktiv.")

# --- NEU: Metadata Extractors ---
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
        self.delete_chat_embeddings(chat_id)

        batch = self.db.batch()
        operation_count = 0
        total_chunks = 0
        skipped_count = 0

        if custom_metadata is None: custom_metadata = {}

        # --- NEU: Classifier initialisieren ---
        classifier = ChunkClassifier() if ChunkClassifier else None
        # --------------------------------------

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

                # Basis-Metadaten
                meta = {"role": role, "source_length": len(content)}
                meta.update(custom_metadata)

                # --- NEU: Automatische Metadaten-Anreicherung (Datum/Version) ---
                # Extrahiert Infos aus dem Titel, bevor der Content-Classifier läuft
                chat_title = meta.get('chat_title', '')
                # Fallback für Speaker, falls noch nicht gesetzt
                speaker_hint = meta.get('speaker') or meta.get('model') or role

                if chat_title:
                    if 'date' not in meta or not meta['date']:
                        meta['date'] = extract_date_from_chat_title(chat_title)

                    if 'version' not in meta or not meta['version']:
                        meta['version'] = extract_version_from_chat_title(chat_title, speaker_hint)
                # ---------------------------------------------------------------

                # --- NEU: Metadaten anreichern (Classifier) ---
                if classifier:
                    meta = classifier.process_chunk(chunk_text, meta)
                # ---------------------------------
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

    def semantic_search(self, query: str, limit: int = 10, filter_role: str = None, allowed_chat_ids: List[str] = None) -> List[Dict]:
        query_vector = self._get_embedding(query)
        if not query_vector: return [], None

        collection_ref = self.db.collection(COLLECTION_NAME)

        # Limit cap bei 1000 (Firestore Hard Limit) - BEIBEHALTEN!
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

            # --- NEU: On-the-fly Metadaten-Reparatur für v47.3 ---
            # Sorgt dafür, dass alte Chunks sofort Datum/Version haben
            if 'chat_title' in meta:
                changed = False
                if not meta.get('date'):
                    meta['date'] = extract_date_from_chat_title(meta['chat_title'])
                    changed = True

                if not meta.get('version'):
                    spk = meta.get('model_name') or meta.get('speaker') or meta.get('role')
                    meta['version'] = extract_version_from_chat_title(meta['chat_title'], spk)
                    changed = True

                # Update für die aktuelle Anzeige (nicht DB-Write)
                if changed:
                    data['metadata'] = meta
            # -----------------------------------------------------

            role = meta.get('role', 'unknown')            


            role = meta.get('role', 'unknown')
            if filter_role and filter_role.lower() != role.lower(): continue

            # Embedding umwandeln (Fix für 0.0% Relevanz) - BEIBEHALTEN!
            if 'embedding' in data:
                vec_obj = data['embedding']
                try:
                    data['embedding_vector'] = list(vec_obj)
                except:
                    data['embedding_vector'] = vec_obj

            data['vector_doc_id'] = doc.id
            cleaned_results.append(data)

            if len(cleaned_results) >= limit * 3: break

        print(f"✅ Nach Filterung: {len(cleaned_results)} Treffer übrig.")
        return cleaned_results, query_vector

    def hybrid_search(self, query: str, keywords: List[str], limit: int = 10, filter_role: str = None, allowed_chat_ids: List[str] = None, keyword_weight: float = 0.3) -> Tuple[List[Dict], Any]:
        # 1. Basis-Suche (Semantic)
        vector_results, query_vector = self.semantic_search(
            query, limit=limit, filter_role=filter_role, allowed_chat_ids=allowed_chat_ids
        )

        if not vector_results:
            print("❌ Vektor-Suche lieferte 0 Ergebnisse.")
            return [], query_vector

        # 2. Keyword-Boosting (mit Wortgrenzen) - BEIBEHALTEN!
        print(f"⚖️ Wende Keyword-Boost an (Gewicht: {keyword_weight})...")

        for result in vector_results:
            content = result.get('content', '').lower()

            # Nutze Regex mit Wortgrenzen (\b)
            keyword_matches = sum(
                1 for kw in keywords
                if re.search(r'\b' + re.escape(kw.lower()) + r'\b', content)
            )

            result['_keyword_boost'] = keyword_matches * keyword_weight
            result['_keyword_matches'] = keyword_matches

        # 3. Sortieren (Boost + Score)
        vector_results.sort(key=lambda x: x.get('_keyword_boost', 0) + x.get('score', 0), reverse=True)

        return vector_results[:limit], query_vector