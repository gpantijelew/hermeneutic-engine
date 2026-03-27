# modules/vector_store.py - v50.9: ChromaDB + sentence-transformers (Drop-in)
"""
Local Vector Store — Drop-in-Ersatz für FirestoreVectorStore.

MIGRATION v50.9:
- Gemini Embeddings  → intfloat/multilingual-e5-large (lokal, CUDA)
- Firestore Vector   → ChromaDB (lokal, persistent)
- Firestore Batches  → ChromaDB upsert()
- Identische öffentliche Schnittstelle: kein anderes Modul muss geändert werden

VOLLSTÄNDIG ERHALTEN:
- BM25Cache (Thread-Safe Singleton)
- chunk_text() mit Speaker-Context-Injection
- hybrid_search_rrf() mit RRF-Fusion
- VIP-Schutz und Fairness-Quota
- Alle Metadaten-Extraktoren

ÄNDERUNGSHISTORIE:
- v50.9: Migration von Firestore/Gemini → ChromaDB/sentence-transformers
- v50.7: AUDIT-FIX (Thread-Safety + Cleanup)
- v50.3: RRF mit VIP-Schutz
- v50.2: Investigativ-Modus mit Fairness-Quota
- v50.1: RRF, Multilinguale Query-Expansion
- v49:   Initiale Version
"""

import os
import logging
import time
import uuid
import re
import threading
import numpy as np
from typing import List, Dict, Optional, Any, Tuple

# ChromaDB
import chromadb
from chromadb.config import Settings as ChromaSettings

# sentence-transformers (lokal, CUDA)
import torch
from sentence_transformers import SentenceTransformer

# Config
from modules.config import (
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    CHROMA_PATH
)

# BM25 für RRF (optional)
try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logging.warning(
        "⚠️ rank-bm25 nicht installiert. RRF läuft im Fallback-Modus. "
        "Installation: pip install rank-bm25"
    )

# Pre-Processing (optional)
try:
    from modules.preprocessing.chunk_classifier import ChunkClassifier
except ImportError:
    ChunkClassifier = None
    logging.warning(
        "⚠️ ChunkClassifier nicht verfügbar. "
        "Metadata-Anreicherung (Chunk-Typen) wird übersprungen."
    )

# Metadata Extractors
from modules.utils.date_extractor import extract_date_from_chat_title
from modules.utils.version_extractor import extract_version_from_chat_title

# Logging
logger = logging.getLogger(__name__)

# Konstanten
COLLECTION_NAME = "hre_chunks"
RRF_K = 60  # Reciprocal Rank Fusion Konstante

# ==============================================================================
# EMBEDDING MODEL SINGLETON (einmal laden, immer verwenden)
# ==============================================================================
_embedding_model: Optional[SentenceTransformer] = None
_embedding_lock = threading.Lock()

def _get_embedding_model() -> SentenceTransformer:
    """
    Thread-safe Singleton für das Embedding-Modell.
    Lädt intfloat/multilingual-e5-large einmalig auf CUDA (falls verfügbar).
    """
    global _embedding_model
    if _embedding_model is None:
        with _embedding_lock:
            if _embedding_model is None:
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                logger.info(
                    f"🔄 Lade Embedding-Modell: {EMBEDDING_MODEL} "
                    f"(device={device})..."
                )
                _embedding_model = SentenceTransformer(
                    EMBEDDING_MODEL,
                    device=device
                )
                logger.info(
                    f"✅ Embedding-Modell geladen. "
                    f"Dimensionen: {EMBEDDING_DIMENSIONS}"
                )
    return _embedding_model

# ==============================================================================
# CHROMADB CLIENT SINGLETON
# ==============================================================================
_chroma_client: Optional[chromadb.PersistentClient] = None
_chroma_collection = None
_chroma_lock = threading.Lock()

def _get_chroma_collection():
    """
    Thread-safe Singleton für ChromaDB Collection.
    Persistiert unter CHROMA_PATH (hre_data/chroma/).
    """
    global _chroma_client, _chroma_collection
    if _chroma_collection is None:
        with _chroma_lock:
            if _chroma_collection is None:
                CHROMA_PATH.mkdir(parents=True, exist_ok=True)
                _chroma_client = chromadb.PersistentClient(
                    path=str(CHROMA_PATH),
                    settings=ChromaSettings(anonymized_telemetry=False)
                )
                _chroma_collection = _chroma_client.get_or_create_collection(
                    name=COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"}
                )
                count = _chroma_collection.count()
                logger.info(
                    f"✅ ChromaDB verbunden: {CHROMA_PATH} "
                    f"({count} Chunks indiziert)"
                )
    return _chroma_collection

# ==============================================================================
# THREAD-SAFE BM25-CACHE (unverändert v50.7)
# ==============================================================================
class BM25Cache:
    """
    Thread-safe Singleton für BM25-Index.
    Vollständig unverändert gegenüber v50.7.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.index = None
                    cls._instance.doc_map = None
                    cls._instance.last_build_time = 0
        return cls._instance

    def get_index(self) -> Tuple[Optional[Any], Optional[Dict]]:
        with self._lock:
            return self.index, self.doc_map

    def set_index(self, index, doc_map):
        with self._lock:
            self.index = index
            self.doc_map = doc_map
            self.last_build_time = time.time()
            logger.info(f"🔄 BM25-Cache aktualisiert. Docs: {len(doc_map)}")

    def invalidate(self):
        with self._lock:
            self.index = None
            self.doc_map = None
            self.last_build_time = 0
            logger.info("🗑️ BM25-Cache invalidiert.")

# ==============================================================================
# LOCAL VECTOR STORE
# ==============================================================================
class FirestoreVectorStore:
    """
    Drop-in-Ersatz für den alten FirestoreVectorStore.
    Name bewusst beibehalten für Rückwärtskompatibilität.

    Intern: ChromaDB + sentence-transformers statt Firestore + Gemini.
    Öffentliche Schnittstelle: identisch.
    """

    def __init__(self, db_client=None):
        """
        db_client wird aus Kompatibilitätsgründen akzeptiert aber ignoriert.
        Alle Verbindungen laufen über Singletons.
        """
        # db_client intentionally ignored — SQLite via database.py Singleton
        if db_client is not None:
            logger.debug(
                "ℹ️ db_client Parameter ignoriert (Migration v50.9: "
                "ChromaDB ersetzt Firestore)."
            )

    # ==========================================================================
    # EMBEDDING (LOKAL)
    # ==========================================================================

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Erzeugt Embedding lokal via sentence-transformers.
        Verwendet 'passage:'-Präfix für zu indizierende Texte (e5-Konvention).
        """
        if not text or not text.strip():
            return None
        try:
            model = _get_embedding_model()
            embedding = model.encode(
                f"passage: {text}",
                normalize_embeddings=True,
                show_progress_bar=False
            )
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"⚠️ Embedding-Fehler: {e}")
            return None

    def _get_query_embedding(self, text: str) -> Optional[List[float]]:
        """
        Erzeugt Query-Embedding mit 'query:'-Präfix (e5-Konvention).
        Separater Einstiegspunkt für Suchanfragen.
        """
        if not text or not text.strip():
            return None
        try:
            model = _get_embedding_model()
            embedding = model.encode(
                f"query: {text}",
                normalize_embeddings=True,
                show_progress_bar=False
            )
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"⚠️ Query-Embedding-Fehler: {e}")
            return None

    # ==========================================================================
    # CHUNKING (vollständig unverändert v50.7)
    # ==========================================================================

    def chunk_text(
        self,
        text: str,
        max_tokens: int = 1000,
        overlap: int = 300
    ) -> List[str]:
        """
        Intelligentes Text-Chunking mit Speaker-Context-Injection.
        Vollständig unverändert gegenüber v50.7.
        """
        if not text:
            return []

        chunk_size_chars = max_tokens * 4
        overlap_chars = overlap * 4

        speaker_pattern = re.compile(
            r"(?:\*\*|#)?\s*Modell:?\s*(.*?)(?:\*\*|$|\n)",
            re.IGNORECASE
        )
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

            current_speaker = None
            for match in speaker_matches:
                if match.start() < end:
                    current_speaker = match.group(1).strip()
                else:
                    break

            final_chunk = raw_chunk
            if current_speaker and f"Modell: {current_speaker}" not in raw_chunk[:50]:
                final_chunk = f"[Kontext: Sprecher ist {current_speaker}] {raw_chunk}"

            chunks.append(final_chunk)
            start = end - overlap_chars

        return chunks

    # ==========================================================================
    # IMPORT & INDEXING
    # ==========================================================================

    def process_and_store_chat(
        self,
        chat_id: str,
        messages: List[Dict],
        custom_metadata: Dict = None
    ) -> Tuple[int, int]:
        """
        Importiert Chat-Nachrichten und speichert Embeddings in ChromaDB.
        Identische Signatur und Semantik zur Firestore-Version.
        """
        logger.info(f"🔄 Starte Vektorisierung für Chat {chat_id}...")

        # 1. Cache invalidieren
        cache = BM25Cache()
        cache.invalidate()

        # 2. Alte Vektoren löschen (Reimport-Sicherheit)
        self.delete_chat_embeddings(chat_id)

        collection = _get_chroma_collection()

        total_chunks = 0
        skipped_chunks = 0

        if custom_metadata is None:
            custom_metadata = {}

        # ChunkClassifier (optional)
        classifier = ChunkClassifier() if ChunkClassifier else None

        # Batch-Akkumulatoren für ChromaDB
        batch_ids = []
        batch_embeddings = []
        batch_documents = []
        batch_metadatas = []
        BATCH_SIZE = 100  # ChromaDB verträgt große Batches problemlos

        for msg in messages:
            content = msg.get('content', '')
            role = msg.get('role') or msg.get('author') or 'unknown'
            msg_id = msg.get('id', str(uuid.uuid4()))

            if not content or len(content.strip()) < 50:
                continue

            chunks = self.chunk_text(content)

            for i, chunk_text_str in enumerate(chunks):
                vec = self._get_embedding(chunk_text_str)
                if not vec:
                    logger.warning(
                        f"⚠️ Chunk {i} von Nachricht {msg_id}: "
                        f"Embedding fehlgeschlagen."
                    )
                    skipped_chunks += 1
                    continue

                doc_id = f"{chat_id}_{msg_id}_{i}"

                # Metadaten aufbauen
                meta = {
                    "chat_id": chat_id,
                    "message_id": msg_id,
                    "chunk_index": i,
                    "role": role,
                    "source_length": len(content)
                }
                meta.update(custom_metadata)

                # Metadata Extraction
                chat_title = meta.get('chat_title', '')
                speaker_hint = (
                    meta.get('speaker') or
                    meta.get('model') or
                    role
                )

                if chat_title:
                    if not meta.get('date'):
                        meta['date'] = extract_date_from_chat_title(
                            chat_title
                        ) or ''
                    if not meta.get('version'):
                        meta['version'] = extract_version_from_chat_title(
                            chat_title, speaker_hint
                        ) or ''

                # Chunk-Klassifikation (optional)
                if classifier:
                    meta = classifier.process_chunk(chunk_text_str, meta)

                # ChromaDB akzeptiert nur str/int/float/bool in metadata
                # None-Werte bereinigen
                clean_meta = {
                    k: (v if v is not None else '')
                    for k, v in meta.items()
                    if isinstance(v, (str, int, float, bool))
                }

                batch_ids.append(doc_id)
                batch_embeddings.append(vec)
                batch_documents.append(chunk_text_str)
                batch_metadatas.append(clean_meta)
                total_chunks += 1

                # Batch-Commit
                if len(batch_ids) >= BATCH_SIZE:
                    collection.upsert(
                        ids=batch_ids,
                        embeddings=batch_embeddings,
                        documents=batch_documents,
                        metadatas=batch_metadatas
                    )
                    batch_ids, batch_embeddings = [], []
                    batch_documents, batch_metadatas = [], []
                    logger.info(f"  💾 Batch committed. Total: {total_chunks}")

        # Finaler Batch
        if batch_ids:
            collection.upsert(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_documents,
                metadatas=batch_metadatas
            )

        logger.info(
            f"✅ Chat {chat_id}: {total_chunks} Chunks gespeichert, "
            f"{skipped_chunks} übersprungen."
        )
        return total_chunks, skipped_chunks

    def delete_chat_embeddings(self, chat_id: str):
        """
        Löscht alle Embeddings für einen Chat aus ChromaDB.
        Identische Semantik zur Firestore-Version.
        """
        try:
            collection = _get_chroma_collection()
            collection.delete(where={"chat_id": chat_id})
            cache = BM25Cache()
            cache.invalidate()
            logger.info(f"🗑️ Embeddings für Chat {chat_id} gelöscht.")
        except Exception as e:
            logger.warning(f"⚠️ Fehler beim Löschen der Embeddings: {e}")

    # ==========================================================================
    # BM25 INDEX MANAGEMENT
    # ==========================================================================

    def _ensure_bm25_index(self):
        """
        Baut BM25-Index auf, falls noch nicht vorhanden (Lazy Loading).
        Datenquelle: ChromaDB statt Firestore.
        Logik vollständig identisch zur v50.7.
        """
        cache = BM25Cache()
        index, doc_map = cache.get_index()

        if index is not None:
            return

        if not BM25_AVAILABLE:
            logger.debug("📚 BM25 nicht verfügbar (Library fehlt).")
            return

        logger.info("🏗️ Baue BM25-Index auf...")
        start = time.time()

        collection = _get_chroma_collection()
        total = collection.count()

        if total == 0:
            logger.warning("⚠️ Keine Dokumente für BM25-Index gefunden.")
            return

        # Alle Dokumente aus ChromaDB laden (in Batches für große Korpora)
        corpus = []
        doc_map = {}
        count = 0
        FETCH_BATCH = 5000

        offset = 0
        while offset < total:
            result = collection.get(
                limit=FETCH_BATCH,
                offset=offset,
                include=["documents", "metadatas"]
            )
            for i, doc_id in enumerate(result['ids']):
                content = result['documents'][i] if result['documents'] else ''
                meta = result['metadatas'][i] if result['metadatas'] else {}
                d = {
                    'vector_doc_id': doc_id,
                    'content': content,
                    'metadata': meta,
                    'chat_id': meta.get('chat_id', '')
                }
                corpus.append(content.lower().split())
                doc_map[count] = d
                count += 1
            offset += FETCH_BATCH

        if corpus:
            bm25_index = BM25Okapi(corpus)
            cache.set_index(bm25_index, doc_map)
            elapsed = time.time() - start
            logger.info(
                f"✅ BM25-Index gebaut: {count} Dokumente in {elapsed:.2f}s"
            )
        else:
            logger.warning("⚠️ Keine Dokumente für BM25-Index gefunden.")

    # ==========================================================================
    # HELPER FUNCTIONS
    # ==========================================================================

    def _cosine_similarity(self, vec_a, vec_b) -> float:
        """Cosine Similarity. Vollständig unverändert."""
        return np.dot(vec_a, vec_b) / (
            np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
        )

    def _get_chat_title(self, chat_id: str) -> str:
        """
        Holt Chat-Titel aus SQLite (via database.py Singleton).
        Vorher: Firestore-Lookup.
        """
        try:
            from modules.database import get_db_connection
            db = get_db_connection()
            if db:
                row = db.execute(
                    "SELECT title FROM chats WHERE id = ?",
                    (chat_id,)
                ).fetchone()
                if row:
                    return row['title'] or f'Doc {chat_id[-8:]}'
            return f'Doc {chat_id[-8:]}'
        except Exception as e:
            logger.warning(
                f"⚠️ Konnte Titel für {chat_id[-8:]} nicht laden: {e}"
            )
            return f'Doc {chat_id[-8:]}'

    # ==========================================================================
    # SEMANTIC SEARCH
    # ==========================================================================

    def semantic_search(
        self,
        query: str,
        limit: int = 10,
        filter_role: str = None,
        allowed_chat_ids: List[str] = None
    ) -> Tuple[List[Dict], List[float]]:
        """
        Vektor-Suche via ChromaDB.
        Identische öffentliche Schnittstelle zur Firestore-Version.
        Investigativ-Modus (Fairness-Quota) vollständig erhalten.
        """
        query_vector = self._get_query_embedding(query)
        if not query_vector:
            logger.error("❌ Konnte Query-Embedding nicht erzeugen.")
            return [], None

        collection = _get_chroma_collection()

        # ======================================================================
        # INVESTIGATIV-MODUS (Fairness-Quota — unveränderte Logik)
        # ======================================================================
        if allowed_chat_ids and len(allowed_chat_ids) <= 5:
            logger.info(
                f"🕵️‍♂️ Investigativ-Modus: {len(allowed_chat_ids)} Dokumente..."
            )

            docs_by_chat = {cid: [] for cid in allowed_chat_ids}

            # Alle Chunks der ausgewählten Chats aus ChromaDB laden
            where_filter = {"chat_id": {"$in": allowed_chat_ids}}

            results = collection.get(
                where=where_filter,
                include=["documents", "metadatas", "embeddings"]
            )

            q_vec_np = np.array(query_vector)

            for i, doc_id in enumerate(results['ids']):
                meta = results['metadatas'][i] if results['metadatas'] else {}

                # Role-Filter
                if filter_role and filter_role.lower() not in \
                        meta.get('role', '').lower():
                    continue

                vec = results['embeddings'][i] if results['embeddings'] else None
                if vec is None:
                    continue

                vec_np = np.array(vec)
                score = self._cosine_similarity(q_vec_np, vec_np)

                data = {
                    'vector_doc_id': doc_id,
                    'content': results['documents'][i] if results['documents'] else '',
                    'metadata': meta,
                    'chat_id': meta.get('chat_id', ''),
                    'score': float(score)
                }

                cid = meta.get('chat_id', '')
                if cid in docs_by_chat:
                    docs_by_chat[cid].append(data)

            # Fairness-Quota
            quota_per_doc = max(20, (limit * 2) // len(allowed_chat_ids))
            logger.info(
                f"⚖️ Fairness-Quota: {quota_per_doc} Chunks pro Dokument"
            )

            fair_candidates = []
            for cid, chunks in docs_by_chat.items():
                if not chunks:
                    chat_title = self._get_chat_title(cid)
                    logger.warning(
                        f"  ⚠️ {chat_title}: Keine Chunks gefunden "
                        "(Filter zu strikt?)"
                    )
                    continue

                chunks.sort(key=lambda x: x['score'], reverse=True)
                selected_count = min(len(chunks), quota_per_doc)
                fair_candidates.extend(chunks[:selected_count])

                chat_title = self._get_chat_title(cid)
                avg_score = sum(
                    c['score'] for c in chunks[:selected_count]
                ) / selected_count
                logger.info(
                    f"  📄 {chat_title}: {len(chunks)} total → "
                    f"{selected_count} selected (Ø Score: {avg_score:.2f})"
                )

            fair_candidates.sort(key=lambda x: x['score'], reverse=True)
            logger.info(
                f"✅ Fairness-Quota: {len(fair_candidates)} Chunks "
                f"aus {len(allowed_chat_ids)} Dokumenten"
            )
            return fair_candidates[:limit * 2], query_vector

        # ======================================================================
        # GLOBALE SUCHE (Standard-Modus)
        # ======================================================================
        where_filter = None
        if allowed_chat_ids:
            where_filter = {"chat_id": {"$in": allowed_chat_ids}}
        if filter_role:
            role_filter = {"role": {"$contains": filter_role.lower()}}
            where_filter = (
                {"$and": [where_filter, role_filter]}
                if where_filter else role_filter
            )

        query_kwargs = dict(
            query_embeddings=[query_vector],
            n_results=min(limit * 2, collection.count() or 1),
            include=["documents", "metadatas", "distances"]
        )
        if where_filter:
            query_kwargs["where"] = where_filter

        results = collection.query(**query_kwargs)

        cleaned_results = []
        for i, doc_id in enumerate(results['ids'][0]):
            meta = results['metadatas'][0][i] if results['metadatas'] else {}
            distance = results['distances'][0][i] if results['distances'] else 1.0

            # Metadata anreichern (Fallback für alte Einträge)
            chat_title = meta.get('chat_title', '')
            if chat_title:
                changed = False
                if not meta.get('date'):
                    meta['date'] = extract_date_from_chat_title(chat_title)
                    changed = True
                if not meta.get('version'):
                    spk = (
                        meta.get('model_name') or
                        meta.get('speaker') or
                        meta.get('role')
                    )
                    meta['version'] = extract_version_from_chat_title(
                        chat_title, spk
                    )
                    changed = True

            data = {
                'vector_doc_id': doc_id,
                'content': results['documents'][0][i] if results['documents'] else '',
                'metadata': meta,
                'chat_id': meta.get('chat_id', ''),
                # ChromaDB Cosine Distance → Score (1 - distance)
                'score': float(1.0 - distance)
            }
            cleaned_results.append(data)

        return cleaned_results, query_vector

    # ==========================================================================
    # HYBRID SEARCH (RRF) — vollständig unverändert v50.7
    # ==========================================================================

    def hybrid_search_rrf(
        self,
        query: str,
        limit: int = 10,
        filter_role: str = None,
        allowed_chat_ids: List[str] = None
    ) -> Tuple[List[Dict], Any]:
        """
        Hybrid-Suche: Semantic + BM25 mit RRF-Fusion.
        VIP-Schutz + Fairness-Quota vollständig erhalten.
        Vollständig unverändert gegenüber v50.7.
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

        # 2. BM25-Suche
        self._ensure_bm25_index()

        bm25_candidates = []
        cache = BM25Cache()
        index, doc_map = cache.get_index()

        if index:
            tokenized_query = query.lower().split()
            top_n_indices = index.get_top_n(
                tokenized_query,
                list(doc_map.keys()),
                n=2000
            )

            for idx in top_n_indices:
                doc_data = doc_map[idx]

                if allowed_chat_ids and \
                        doc_data.get('chat_id') not in allowed_chat_ids:
                    continue

                if filter_role and filter_role.lower() not in \
                        doc_data.get('metadata', {}).get('role', '').lower():
                    continue

                bm25_candidates.append(doc_data)

                if len(bm25_candidates) >= limit * 3:
                    break

            logger.info(f"📚 BM25-Suche: {len(bm25_candidates)} Treffer.")

        # 3. RRF-Fusion
        rrf_scores = {}

        def add_scores(candidates, weight=1.0):
            for rank, doc in enumerate(candidates):
                doc_id = doc.get('vector_doc_id')
                if not doc_id:
                    continue
                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = {"doc": doc, "score": 0.0}
                rrf_scores[doc_id]["score"] += weight * (
                    1 / (RRF_K + rank + 1)
                )

        add_scores(vector_candidates)
        add_scores(bm25_candidates)

        sorted_results = sorted(
            rrf_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )

        # ======================================================================
        # VIP-SCHUTZ (unverändert v50.3)
        # ======================================================================
        final_results = []

        if allowed_chat_ids and len(allowed_chat_ids) <= 10:
            results_by_chat = {cid: [] for cid in allowed_chat_ids}

            for item in sorted_results:
                doc = item['doc']
                cid = doc.get('chat_id')
                if cid in results_by_chat:
                    results_by_chat[cid].append(doc)

            vip_set = set()
            for cid, docs in results_by_chat.items():
                for d in docs[:3]:
                    uid = d.get('vector_doc_id')
                    if uid and uid not in vip_set:
                        final_results.append(d)
                        vip_set.add(uid)

            logger.info(
                f"🛡️ VIP-Schutz: {len(final_results)} Chunks garantiert."
            )

            for item in sorted_results:
                doc = item['doc']
                uid = doc.get('vector_doc_id')
                if len(final_results) >= limit:
                    break
                if uid and uid not in vip_set:
                    final_results.append(doc)
                    vip_set.add(uid)
        else:
            final_results = [
                item['doc'] for item in sorted_results[:limit]
            ]

        for res in final_results:
            res['_rrf_active'] = True

        logger.info(f"⚖️ RRF Fusion: {len(final_results)} finale Treffer.")
        return final_results, query_vector

    # ==========================================================================
    # CACHE MANAGEMENT (PUBLIC API — unverändert)
    # ==========================================================================

    def invalidate_bm25_cache(self):
        """Invalidiert den BM25-Cache manuell. Unverändert."""
        cache = BM25Cache()
        cache.invalidate()
        logger.info("🗑️ BM25-Cache manuell invalidiert (Public API).")

    # ==========================================================================
    # LEGACY WRAPPER (unverändert)
    # ==========================================================================

    def hybrid_search(
        self,
        query: str,
        keywords: List[str] = None,
        limit: int = 10,
        filter_role: str = None,
        allowed_chat_ids: List[str] = None,
        keyword_weight: float = 0.3
    ) -> Tuple[List[Dict], Any]:
        """Legacy-Wrapper. Unverändert."""
        return self.hybrid_search_rrf(
            query, limit, filter_role, allowed_chat_ids
        )