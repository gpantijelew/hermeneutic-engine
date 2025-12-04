# modules/vector_store.py - DIAGNOSE-VERSION
print("🔍 START: Modul wird geladen...")

import os
print("✅ os importiert")

import logging
print("✅ logging importiert")

import time
print("✅ time importiert")

import uuid
print("✅ uuid importiert")

import re
print("✅ re importiert")

from typing import List, Dict, Optional, Any, Tuple
print("✅ typing importiert")

import google.generativeai as genai
print("✅ google.generativeai importiert")

from google.cloud import firestore
print("✅ firestore importiert")

from google.cloud.firestore_v1.vector import Vector
print("✅ Vector importiert")

from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
print("✅ DistanceMeasure importiert")

print("🎯 ALLE IMPORTS ERFOLGREICH!")

# Logger konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
print("✅ Logger konfiguriert")

# Konfiguration
EMBEDDING_MODEL = "models/text-embedding-004"
DIMENSIONS = 768
COLLECTION_NAME = "embeddings"
print("✅ Konstanten definiert")

# API Key Setup
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
print("✅ API Key Setup abgeschlossen")

# Klassen-Definition beginnt
class FirestoreVectorStore:
    print("✅ Klasse FirestoreVectorStore wird definiert...")
    def __init__(self, db_client: firestore.Client):
        self.db = db_client
        print("✅ __init__ definiert")

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        if not text or not text.strip(): return None
        retries = 3
        for attempt in range(retries):
            try:
                result = genai.embed_content(
                    model=EMBEDDING_MODEL, content=text,
                    task_type="retrieval_document", title=None
                )
                return result['embedding']
            except Exception as e:
                logger.warning(f"⚠️ Embedding Fehler: {e}")
                time.sleep(1)
        return None

   # UPDATE: Größere Chunks (1000 Tokens) und viel mehr Overlap (300 Tokens)
    def chunk_text(self, text: str, max_tokens: int = 1000, overlap: int = 300) -> List[str]:
        """
        Splittet Text in Chunks UND behält den Sprecher-Kontext bei (Sticky Headers).
        """
        if not text: return []

        chunk_size_chars = max_tokens * 4
        overlap_chars = overlap * 4

        # --- UPDATE: Robusterer Regex ---
        # Fängt "**Modell: Name**", "**Model: Name**" und auch ohne Fettdruck "Modell: Name" am Zeilenanfang
        # flag re.IGNORECASE sorgt dafür, dass Groß/Kleinschreibung egal ist
        speaker_pattern = re.compile(r"(?:\*\*|#)?\s*Modell:?\s*(.*?)(?:\*\*|$|\n)", re.IGNORECASE)
        speaker_matches = list(speaker_pattern.finditer(text))
        # -------------------------------

        if len(text) <= chunk_size_chars:
            return [text]

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
                    # Bereinigen des Namens (Leerzeichen weg)
                    current_speaker = m.group(1).strip()

            final_chunk = raw_chunk
            # Wir fügen den Header nur hinzu, wenn er nicht eh schon ganz am Anfang des Chunks steht
            if current_speaker:
                # Checken, ob der Name schon im Chunk vorkommt, um Dopplung zu vermeiden
                if f"Modell: {current_speaker}" not in raw_chunk[:50]: 
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

        for msg in messages:
            content = msg.get('content', '')
            role = msg.get('role') or msg.get('author') or 'unknown'
            msg_id = msg.get('id', str(uuid.uuid4()))

            if not content: continue

            if len(content.strip()) < 70:
                skipped_count += 1
                continue

            # Hier wird jetzt die schlaue Chunking-Funktion aufgerufen
            chunks = self.chunk_text(content)

            for i, chunk_text in enumerate(chunks):
                vector_values = self._get_embedding(chunk_text)
                if not vector_values: continue

                doc_id = f"{chat_id}_{msg_id}_{i}"
                doc_ref = self.db.collection(COLLECTION_NAME).document(doc_id)

                meta = {
                    "role": role,
                    "source_length": len(content)
                }
                meta.update(custom_metadata)

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

        if operation_count > 0:
            batch.commit()

        logger.info(f"✅ Chat {chat_id}: {total_chunks} Chunks. Platform: {custom_metadata.get('platform')}")
        return total_chunks, skipped_count

    def delete_chat_embeddings(self, chat_id: str):
        docs = self.db.collection(COLLECTION_NAME).where("chat_id", "==", chat_id).stream()
        for doc in docs:
            doc.reference.delete()

    def semantic_search(self, query: str, limit: int = 10, filter_role: str = None) -> List[Dict]:
        query_vector = self._get_embedding(query)
        if not query_vector: return [], None

        collection_ref = self.db.collection(COLLECTION_NAME)
        fetch_limit = limit * 5 if filter_role else limit

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
            meta = data.get('metadata', {})
            role = meta.get('role', 'unknown')

            if filter_role and filter_role.lower() != role.lower():
                continue

            if 'embedding' in data:
                vec_obj = data['embedding']
                try:
                    data['embedding_vector'] = list(vec_obj) 
                except:
                    data['embedding_vector'] = vec_obj
                del data['embedding']

            data['vector_doc_id'] = doc.id
            cleaned_results.append(data)

            if len(cleaned_results) >= limit:
                break

        return cleaned_results, query_vector

    def hybrid_search(
        self, 
        query: str, 
        keywords: List[str], 
        limit: int = 10, 
        filter_role: str = None
    ) -> Tuple[List[Dict], Any]:
        """
        Hybrid Search: Kombiniert Vektor-Suche mit Keyword-Boosting.
        v46.1 Patch
        """
        # 1. Standard Vektor-Suche (3x Limit für größeren Pool)
        vector_results, query_vector = self.semantic_search(
            query, 
            limit=limit * 3,
            filter_role=filter_role
        )

        if not vector_results:
            return [], query_vector

        # 2. Keyword-Boosting
        for result in vector_results:
            # Content sicher abrufen und normalisieren
            content = result.get('content', '').lower()

            # Zähle Keyword-Matches
            keyword_matches = sum(1 for kw in keywords if kw.lower() in content)

            # Boost-Score berechnen
            # Logik: Ein Match bringt 0.15 Punkte. 
            # Das ist aggressiv genug, um relevante Chunks nach oben zu spülen.
            result['_keyword_boost'] = keyword_matches * 0.15
            result['_keyword_matches'] = keyword_matches

        # 3. Re-Sortierung
        # Wir sortieren primär nach dem Boost, sekundär bleibt die Vektor-Relevanz 
        # erhalten (da Python's sort stabil ist, wenn wir es richtig machen, 
        # aber hier erzwingen wir den Boost als Hauptfaktor).
        vector_results.sort(
            key=lambda x: x.get('_keyword_boost', 0), 
            reverse=True
        )

        # 4. Rückgabe der Top-N
        return vector_results[:limit], query_vector