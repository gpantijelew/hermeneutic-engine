# modules/vector_store.py - v52: ChromaDB + sentence-transformers
"""
Local Vector Store (ChromaDB + sentence-transformers).

MIGRATION v51:
- FirestoreVectorStore → LocalVectorStore (Phase 2.3)

MIGRATION v50.9:
- Gemini Embeddings  → intfloat/multilingual-e5-large (lokal, CUDA)
- Firestore Vector   → ChromaDB (lokal, persistent)
- Firestore Batches  → ChromaDB upsert()

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

import logging
import time
import uuid
import re
import hashlib
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
from modules.config import EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, CHROMA_PATH

# Phase 4.4: Embedding Cache
from modules.database import get_db_connection
from modules.embedding_cache import EmbeddingCache

# Phase 4.3: Chunk Registry (SQLite treibt, ChromaDB folgt)
from modules.database import (
    register_chunks,
    unregister_chat_chunks,
    update_chunk_count,
    get_chunk_ids_page,
    get_chunk_registry_count,
    is_duplicate_chunk,
    backfill_chunk_registry,
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
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info(
                    f"🔄 Lade Embedding-Modell: {EMBEDDING_MODEL} (device={device})..."
                )
                _embedding_model = SentenceTransformer(EMBEDDING_MODEL, device=device)
                logger.info(
                    f"✅ Embedding-Modell geladen. Dimensionen: {EMBEDDING_DIMENSIONS}"
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
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                _chroma_collection = _chroma_client.get_or_create_collection(
                    name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
                )
                count = _chroma_collection.count()
                logger.info(
                    f"✅ ChromaDB verbunden: {CHROMA_PATH} ({count} Chunks indiziert)"
                )
    return _chroma_collection


# ==============================================================================
# THREAD-SAFE BM25-CACHE (v53 — Direct Injection Support)
# ==============================================================================
class BM25Cache:
    """
    Thread-safe Singleton für BM25-Index.
    v53+: Direct Injection — inkrementelle Updates ohne Full-Rebuild.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.bm25 = None
                    cls._instance.corpus: List[List[str]] = []
                    cls._instance.doc_ids: List[str] = []
                    cls._instance.metadata: List[Dict] = []
                    cls._instance.last_build_time = 0
        return cls._instance

    def get_index(self) -> Tuple[Optional[Any], Optional[Dict]]:
        with self._lock:
            if self.bm25 is not None:
                doc_map = {
                    i: {
                        "vector_doc_id": self.doc_ids[i],
                        "content": " ".join(self.corpus[i]),
                        "metadata": self.metadata[i],
                        "chat_id": self.metadata[i].get("chat_id", ""),
                    }
                    for i in range(len(self.doc_ids))
                }
                return self.bm25, doc_map
            return None, None

    def set_index(self, index, doc_map):
        with self._lock:
            self.bm25 = index
            if doc_map:
                self.doc_ids = [doc_map[i]["vector_doc_id"] for i in sorted(doc_map.keys())]
                self.corpus = [doc_map[i]["content"].lower().split() for i in sorted(doc_map.keys())]
                self.metadata = [doc_map[i]["metadata"] for i in sorted(doc_map.keys())]
            else:
                self.doc_ids = []
                self.corpus = []
                self.metadata = []
            self.last_build_time = time.time()
            logger.info(f"🔄 BM25-Cache aktualisiert. Docs: {len(self.doc_ids)}")

    def append_docs(self, new_doc_ids: List[str], new_corpus: List[List[str]], new_metadata: List[Dict]) -> bool:
        """Inkrementelle Erweiterung ohne ChromaDB-Reload."""
        with self._lock:
            if self.bm25 is None:
                return False
            self.doc_ids.extend(new_doc_ids)
            self.corpus.extend(new_corpus)
            self.metadata.extend(new_metadata)
            self.bm25 = BM25Okapi(self.corpus)
            self.last_build_time = time.time()
            logger.info(
                f"➕ BM25 Direct Injection: +{len(new_doc_ids)} Docs "
                f"(Total: {len(self.doc_ids)})"
            )
            return True

    def invalidate(self):
        with self._lock:
            self.bm25 = None
            self.corpus = []
            self.doc_ids = []
            self.metadata = []
            self.last_build_time = 0
            logger.info("🗑️ BM25-Cache invalidiert.")


# ==============================================================================
# LOCAL VECTOR STORE
# ==============================================================================
class LocalVectorStore:
    """
    Lokaler Vector Store basierend auf ChromaDB + sentence-transformers.
    Intern: ChromaDB + sentence-transformers.
    Öffentliche Schnittstelle: identisch zur alten Firestore-Version.
    """

    def __init__(self, db_client=None):
        """
        db_client wird aus Kompatibilitätsgründen akzeptiert aber ignoriert.
        Alle Verbindungen laufen über Singletons.
        """
        # db_client intentionally ignored — SQLite via database.py Singleton
        if db_client is not None:
            logger.debug(
                "ℹ️ db_client Parameter ignoriert (LocalVectorStore nutzt Singletons)."
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
                f"passage: {text}", normalize_embeddings=True, show_progress_bar=False
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
                f"query: {text}", normalize_embeddings=True, show_progress_bar=False
            )
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"⚠️ Query-Embedding-Fehler: {e}")
            return None

    def _get_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Erzeugt Embeddings im Batch via sentence-transformers (DeepSeek Performance Fix).
        Gibt Liste von Embeddings zurück (None für fehlgeschlagene Texte).
        """
        if not texts:
            return []
        try:
            model = _get_embedding_model()
            prefixed = [f"passage: {t}" for t in texts]
            embeddings = model.encode(
                prefixed,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=32,
            )
            return [e.tolist() for e in embeddings]
        except Exception as e:
            logger.error(f"❌ Batch-Embedding fehlgeschlagen: {e}")
            return [None] * len(texts)

    # ==========================================================================
    # CHUNKING (vollständig unverändert v50.7)
    # ==========================================================================

    def chunk_text(
        self, text: str, max_tokens: int = 1000, overlap: int = 300
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
            r"(?:\*\*|#)?\s*Modell:?\s*(.*?)(?:\*\*|$|\n)", re.IGNORECASE
        )
        speaker_matches = list(speaker_pattern.finditer(text))

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size_chars

            if end < len(text):
                last_period = text.rfind(".", start, end)
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
        self, chat_id: str, messages: List[Dict], custom_metadata: Dict = None
    ) -> Tuple[int, int]:
        """
        Importiert Chat-Nachrichten und speichert Embeddings in ChromaDB.
        Identische Signatur und Semantik zur Vorgänger-Version.
        """
        logger.info(f"🔄 Starte Vektorisierung für Chat {chat_id}...")

        # Phase 4.2: BM25 Direct Injection — kein Full-Rebuild bei Import

        # 1. Alte Vektoren löschen (Reimport-Sicherheit)
        self.delete_chat_embeddings(chat_id)

        collection = _get_chroma_collection()

        total_chunks = 0
        skipped_chunks = 0

        if custom_metadata is None:
            custom_metadata = {}

        # ChunkClassifier (optional)
        classifier = ChunkClassifier() if ChunkClassifier else None

        # Phase 4.4: Embedding Cache Initialisieren
        db = get_db_connection()
        emb_cache = EmbeddingCache(db) if db else None
        pending_cache_writes = []
        cache_hits = 0

        # Batch-Akkumulatoren für ChromaDB
        batch_ids = []
        batch_embeddings = []
        batch_documents = []
        batch_metadatas = []
        batch_hashes = []
        BATCH_SIZE = 100  # ChromaDB verträgt große Batches problemlos

        # Phase 4.3: Alle erfolgreich eingefügten doc_ids sammeln für Registry
        # A.13: Auch content_hashes sammeln für Deduplizierung
        all_inserted_doc_ids = []
        all_inserted_hashes = []

        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role") or msg.get("author") or "unknown"
            msg_id = msg.get("id", str(uuid.uuid4()))

            if not content or len(content.strip()) < 50:
                continue

            chunks = self.chunk_text(content)

            # --- DEEPSEEK PERFORMANCE FIX: BATCH PREPARATION ---
            chunk_vectors = [None] * len(chunks)
            texts_to_embed = []
            indices_to_embed = []

            # 1. Cache prüfen
            for i, chunk_text_str in enumerate(chunks):
                vec = None
                if emb_cache:
                    vec = emb_cache.get(chunk_text_str)
                    if vec:
                        cache_hits += 1

                if vec:
                    chunk_vectors[i] = vec
                else:
                    texts_to_embed.append(chunk_text_str)
                    indices_to_embed.append(i)

            # 2. Batch Encoding für alle nicht-gecachten Chunks dieser Nachricht
            if texts_to_embed:
                new_vecs = self._get_embeddings_batch(texts_to_embed)
                for idx, vec in zip(indices_to_embed, new_vecs):
                    chunk_vectors[idx] = vec
                    if vec and emb_cache:
                        pending_cache_writes.append((chunks[idx], vec))

            # 3. Bestehende Logik anwenden (Metadaten & ChromaDB)
            for i, chunk_text_str in enumerate(chunks):
                vec = chunk_vectors[i]

                if not vec:
                    logger.warning(f"⚠️ Chunk {i} von Nachricht {msg_id}: Embedding fehlgeschlagen.")
                    skipped_chunks += 1
                    continue

                # A.13 Deduplication: SHA-256 Hash prüfen
                content_hash = hashlib.sha256(chunk_text_str.encode("utf-8")).hexdigest()
                if is_duplicate_chunk(content_hash):
                    skipped_chunks += 1
                    logger.info(f"🚫 Chunk {i} dedupliziert (Hash {content_hash[:8]}... bereits in Registry)")
                    continue

                doc_id = f"{chat_id}_{msg_id}_{i}"

                # Metadaten aufbauen
                meta = {
                    "chat_id": chat_id,
                    "message_id": msg_id,
                    "chunk_index": i,
                    "role": role,
                    "source_length": len(content),
                    "content_hash": content_hash,
                }
                meta.update(custom_metadata)

                # Metadata Extraction
                chat_title = meta.get("chat_title", "")
                speaker_hint = meta.get("speaker") or meta.get("model") or role

                if chat_title:
                    if not meta.get("date"):
                        meta["date"] = extract_date_from_chat_title(chat_title) or ""
                    if not meta.get("version"):
                        meta["version"] = (
                            extract_version_from_chat_title(chat_title, speaker_hint)
                            or ""
                        )

                # Chunk-Klassifikation (optional)
                if classifier:
                    meta = classifier.process_chunk(chunk_text_str, meta)

                # ChromaDB akzeptiert nur str/int/float/bool in metadata
                # None-Werte bereinigen
                clean_meta = {
                    k: (v if v is not None else "")
                    for k, v in meta.items()
                    if isinstance(v, (str, int, float, bool))
                }

                batch_ids.append(doc_id)
                batch_embeddings.append(vec)
                batch_documents.append(chunk_text_str)
                batch_metadatas.append(clean_meta)
                batch_hashes.append(content_hash)
                total_chunks += 1

                # Batch-Commit (ROBUSTE VERSION)
                if len(batch_ids) >= BATCH_SIZE:
                    try:
                        collection.upsert(
                            ids=batch_ids,
                            embeddings=batch_embeddings,
                            documents=batch_documents,
                            metadatas=batch_metadatas,
                        )

                        # NUR bei Erfolg: Embedding Cache committen
                        if emb_cache and pending_cache_writes:
                            try:
                                for text, embedding in pending_cache_writes:
                                    emb_cache.set(text, embedding)
                                db.commit()
                                logger.info(f"  💾 Embedding Cache: {len(pending_cache_writes)} neue Einträge gespeichert.")
                            except Exception as cache_err:
                                logger.warning(f"⚠️ Embedding Cache-Commit fehlgeschlagen: {cache_err}")

                        # Phase 4.2: BM25 Direct Injection
                        bm25_cache = BM25Cache()
                        if bm25_cache.bm25 is not None:
                            new_corpus = [doc.lower().split() for doc in batch_documents]
                            bm25_cache.append_docs(batch_ids, new_corpus, batch_metadatas)

                        # Phase 4.3: Erfolgreich eingefügte IDs + Hashes für Registry sammeln
                        all_inserted_doc_ids.extend(batch_ids)
                        all_inserted_hashes.extend(batch_hashes)

                        logger.info(f"  💾 Batch committed. Total: {total_chunks}")

                    except Exception as e:
                        logger.error(f"❌ ChromaDB Batch-Commit fehlgeschlagen: {e}")
                        logger.warning(f"⚠️ {len(batch_ids)} Chunks wurden übersprungen. Cache wird nicht aktualisiert.")

                    finally:
                        # IMMER leeren, um Endlos-Retries bei jedem weiteren Chunk zu verhindern!
                        batch_ids, batch_embeddings = [], []
                        batch_documents, batch_metadatas = [], []
                        batch_hashes = []
                        pending_cache_writes = []

        # Finaler Batch (ROBUSTE VERSION)
        if batch_ids:
            try:
                collection.upsert(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    documents=batch_documents,
                    metadatas=batch_metadatas,
                )

                # Phase 4.4: Letzte Cache-Einträge committen
                if emb_cache and pending_cache_writes:
                    try:
                        for text, embedding in pending_cache_writes:
                            emb_cache.set(text, embedding)
                        db.commit()
                        logger.info(f"  💾 Embedding Cache: {len(pending_cache_writes)} finale Einträge gespeichert.")
                    except Exception as cache_err:
                        logger.warning(f"⚠️ Finaler Cache-Commit fehlgeschlagen: {cache_err}")

                # Phase 4.2: BM25 Direct Injection
                bm25_cache = BM25Cache()
                if bm25_cache.bm25 is not None:
                    new_corpus = [doc.lower().split() for doc in batch_documents]
                    bm25_cache.append_docs(batch_ids, new_corpus, batch_metadatas)

                # Phase 4.3: Finale Batch-IDs + Hashes sammeln
                all_inserted_doc_ids.extend(batch_ids)
                all_inserted_hashes.extend(batch_hashes)

            except Exception as e:
                logger.error(f"❌ Finaler ChromaDB Batch-Commit fehlgeschlagen: {e}")
                logger.error(f"   {len(batch_ids)} Chunks wurden NICHT gespeichert!")

        # Phase 4.3: Chunk Registry synchronisieren + chunk_count aktualisieren
        if all_inserted_doc_ids:
            try:
                register_chunks(chat_id, all_inserted_doc_ids, all_inserted_hashes)
                update_chunk_count(chat_id)
            except Exception as e:
                logger.warning(f"⚠️ Chunk Registry Sync fehlgeschlagen: {e}")

        logger.info(
            f"✅ Chat {chat_id}: {total_chunks} Chunks gespeichert, "
            f"{skipped_chunks} übersprungen, {cache_hits} aus Cache geladen."
        )
        # Skipped-Zahl in DB persistieren
        try:
            if db:
                db.execute(
                    "UPDATE chats SET skipped_chunks = ? WHERE id = ?",
                    (skipped_chunks, chat_id),
                )
                db.commit()
        except Exception as e:
            logger.warning(f"⚠️ skipped_chunks konnte nicht gespeichert werden: {e}")
        return total_chunks, skipped_chunks

    def delete_chat_embeddings(self, chat_id: str):
        """
        Löscht alle Embeddings für einen Chat aus ChromaDB.
        Phase 4.3: Synchronisiert auch die Chunk Registry in SQLite.
        """
        try:
            collection = _get_chroma_collection()
            collection.delete(where={"chat_id": chat_id})
            cache = BM25Cache()
            cache.invalidate()
            logger.info(f"🗑️ Embeddings für Chat {chat_id} gelöscht.")
        except Exception as e:
            logger.warning(f"⚠️ Fehler beim Löschen der Embeddings: {e}")

        # Phase 4.3: Registry synchronisieren — unabhängig von ChromaDB-Erfolg
        try:
            unregister_chat_chunks(chat_id)
            update_chunk_count(chat_id)
        except Exception as e:
            logger.warning(f"⚠️ Chunk Registry Sync beim Löschen fehlgeschlagen: {e}")

    def iter_all_chunks(self, limit: int = 0):
        """
        Generator: Gibt alle gespeicherten Chunks einzeln zurück (RAM-schonend).
        Phase 4.3: Nutzt SQLite Registry für stabile Keyset-Pagination
        statt ChromaDB offset (instabil bei Imports/Deletes).

        Args:
            limit: Max. Anzahl Chunks (0 = alle)

        Yields:
            Dict mit: vector_doc_id, content, metadata, chat_id
        """
        collection = _get_chroma_collection()
        total = collection.count()
        if total == 0:
            return

        # Phase 4.3: Lazy Backfill — falls Registry leer (erster Start nach Update)
        registry_count = get_chunk_registry_count()
        if registry_count == 0 and total > 0:
            logger.info("🔄 Chunk Registry leer — starte einmaligen Backfill...")
            backfill_chunk_registry(collection)

        # Phase 4.3: Keyset-Pagination über SQLite Registry
        FETCH_BATCH = 50  # ChromaDB get(ids=[...]) ist effizient
        last_seq = 0
        yielded = 0

        while True:
            chunk_ids, last_seq = get_chunk_ids_page(
                chat_id=None, last_seq=last_seq, limit=FETCH_BATCH
            )
            if not chunk_ids:
                break

            # ChromaDB liefert nur die Vektoren/Dokumente für die IDs
            result = collection.get(
                ids=chunk_ids, include=["documents", "metadatas"]
            )
            # ChromaDB gibt Ergebnisse nicht in Request-Reihenfolge zurück!
            # Index-Map für korrekte Zuordnung bauen
            id_to_idx = {cid: i for i, cid in enumerate(result["ids"])}

            for doc_id in chunk_ids:
                idx = id_to_idx.get(doc_id)
                if idx is None:
                    logger.warning(f"⚠️ Chunk {doc_id} in Registry aber nicht in ChromaDB (Orphan).")
                    continue
                content = result["documents"][idx] if result["documents"] else ""
                meta = result["metadatas"][idx] if result["metadatas"] else {}
                yield {
                    "vector_doc_id": doc_id,
                    "content": content,
                    "metadata": meta,
                    "chat_id": meta.get("chat_id", ""),
                }
                yielded += 1
                if limit > 0 and yielded >= limit:
                    return

    def get_all_chunks(self, limit: int = 0) -> list:
        """
        Legacy-Wrapper für Abwärtskompatibilität.
        Lädt alle Chunks in eine Liste (Achtung: RAM-intensiv bei großen DBs).
        """
        logger.info(f"📦 get_all_chunks: Lade Chunks in den RAM...")
        results = list(self.iter_all_chunks(limit))
        logger.info(f"📦 get_all_chunks: {len(results)} Chunks geladen.")
        return results

    def update_chunk_metadata(self, chunk_id: str, metadata_updates: dict) -> bool:
        """
        Aktualisiert Metadaten eines einzelnen Chunks per ID.
        ChromaDB ersetzt immer die gesamte Metadaten-Dict (kein Partial Update),
        daher: fetch → merge → write.

        Args:
            chunk_id:         vector_doc_id des Chunks
            metadata_updates: Dict mit zu ändernden Feldern.
                              wird automatisch auf Flat-Keys reduziert.

        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            collection = _get_chroma_collection()

            # 1. Existierende Metadaten holen (ChromaDB braucht das komplette Dict)
            existing = collection.get(ids=[chunk_id], include=["metadatas"])
            if not existing["ids"]:
                logger.warning(
                    f"⚠️ update_chunk_metadata: Chunk {chunk_id} nicht gefunden."
                )
                return False

            current_meta = existing["metadatas"][0] if existing["metadatas"] else {}

            # 2. Merge — Dot-Notation ('metadata.model_name') → Flat-Key
            merged = dict(current_meta)
            for key, value in metadata_updates.items():
                flat_key = key.replace("metadata.", "")
                merged[flat_key] = value

            # 3. Zurückschreiben
            collection.update(ids=[chunk_id], metadatas=[merged])
            return True

        except Exception as e:
            logger.error(f"❌ update_chunk_metadata [{chunk_id}]: {e}")
            return False

    # ==========================================================================
    # BM25 INDEX MANAGEMENT
    # ==========================================================================

    def _ensure_bm25_index(self):
        """
        Baut BM25-Index auf, falls noch nicht vorhanden (Lazy Loading).
        Phase 4.3: Nutzt SQLite Registry für stabile Pagination
        statt ChromaDB offset.
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

        # Phase 4.3: Lazy Backfill — falls Registry leer
        registry_count = get_chunk_registry_count()
        if registry_count == 0 and total > 0:
            logger.info("🔄 Chunk Registry leer — starte einmaligen Backfill für BM25...")
            backfill_chunk_registry(collection)

        # Phase 4.3: Pagination über Registry, ChromaDB liefert Dokumente
        corpus = []
        doc_map = {}
        count = 0
        FETCH_BATCH = 500
        last_seq = 0

        while True:
            chunk_ids, last_seq = get_chunk_ids_page(
                chat_id=None, last_seq=last_seq, limit=FETCH_BATCH
            )
            if not chunk_ids:
                break

            result = collection.get(ids=chunk_ids, include=["documents", "metadatas"])
            id_to_idx = {cid: i for i, cid in enumerate(result["ids"])}

            for doc_id in chunk_ids:
                idx = id_to_idx.get(doc_id)
                if idx is None:
                    continue
                content = result["documents"][idx] if result["documents"] else ""
                meta = result["metadatas"][idx] if result["metadatas"] else {}
                d = {
                    "vector_doc_id": doc_id,
                    "content": content,
                    "metadata": meta,
                    "chat_id": meta.get("chat_id", ""),
                }
                corpus.append(content.lower().split())
                doc_map[count] = d
                count += 1

        if corpus:
            bm25_index = BM25Okapi(corpus)
            cache.set_index(bm25_index, doc_map)
            elapsed = time.time() - start
            logger.info(f"✅ BM25-Index gebaut: {count} Dokumente in {elapsed:.2f}s")
        else:
            logger.warning("⚠️ Keine Dokumente für BM25-Index gefunden.")

    # ==========================================================================
    # HELPER FUNCTIONS
    # ==========================================================================

    def _cosine_similarity(self, vec_a, vec_b) -> float:
        """Cosine Similarity. Vollständig unverändert."""
        return np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b))

    def _get_chat_title(self, chat_id: str) -> str:
        """
        Holt Chat-Titel aus SQLite (via database.py Singleton).
        """
        try:
            from modules.database import get_db_connection

            db = get_db_connection()
            if db:
                row = db.execute(
                    "SELECT title FROM chats WHERE id = ?", (chat_id,)
                ).fetchone()
                if row:
                    return row["title"] or f"Doc {chat_id[-8:]}"
            return f"Doc {chat_id[-8:]}"
        except Exception as e:
            logger.warning(f"⚠️ Konnte Titel für {chat_id[-8:]} nicht laden: {e}")
            return f"Doc {chat_id[-8:]}"

    # ==========================================================================
    # SEMANTIC SEARCH
    # ==========================================================================

    def semantic_search(
        self,
        query: str,
        limit: int = 10,
        filter_role: str = None,
        allowed_chat_ids: List[str] = None,
    ) -> Tuple[List[Dict], List[float]]:
        """
        Vektor-Suche via ChromaDB.
        Identische öffentliche Schnittstelle zur Vorgänger-Version.
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
            logger.info(f"🕵️‍♂️ Investigativ-Modus: {len(allowed_chat_ids)} Dokumente...")

            docs_by_chat = {cid: [] for cid in allowed_chat_ids}

            # Alle Chunks der ausgewählten Chats aus ChromaDB laden
            where_filter = {"chat_id": {"$in": allowed_chat_ids}}

            results = collection.get(
                where=where_filter, include=["documents", "metadatas", "embeddings"]
            )

            q_vec_np = np.array(query_vector)

            for i, doc_id in enumerate(results["ids"]):
                meta = results["metadatas"][i] if results["metadatas"] else {}

                # Role-Filter
                if (
                    filter_role
                    and filter_role.lower() not in meta.get("role", "").lower()
                ):
                    continue

                vec = (
                    results["embeddings"][i]
                    if results["embeddings"] is not None
                    else None
                )
                if vec is None:
                    continue

                vec_np = np.array(vec)
                score = self._cosine_similarity(q_vec_np, vec_np)

                data = {
                    "vector_doc_id": doc_id,
                    "content": results["documents"][i] if results["documents"] else "",
                    "metadata": meta,
                    "chat_id": meta.get("chat_id", ""),
                    "score": float(score),
                    "embedding": vec,
                }

                cid = meta.get("chat_id", "")
                if cid in docs_by_chat:
                    docs_by_chat[cid].append(data)

            # Fairness-Quota
            quota_per_doc = max(20, (limit * 2) // len(allowed_chat_ids))
            logger.info(f"⚖️ Fairness-Quota: {quota_per_doc} Chunks pro Dokument")

            fair_candidates = []
            for cid, chunks in docs_by_chat.items():
                if not chunks:
                    chat_title = self._get_chat_title(cid)
                    logger.warning(
                        f"  ⚠️ {chat_title}: Keine Chunks gefunden (Filter zu strikt?)"
                    )
                    continue

                chunks.sort(key=lambda x: x["score"], reverse=True)
                selected_count = min(len(chunks), quota_per_doc)
                fair_candidates.extend(chunks[:selected_count])

                chat_title = self._get_chat_title(cid)
                avg_score = (
                    sum(c["score"] for c in chunks[:selected_count]) / selected_count
                )
                logger.info(
                    f"  📄 {chat_title}: {len(chunks)} total → "
                    f"{selected_count} selected (Ø Score: {avg_score:.2f})"
                )

            fair_candidates.sort(key=lambda x: x["score"], reverse=True)
            logger.info(
                f"✅ Fairness-Quota: {len(fair_candidates)} Chunks "
                f"aus {len(allowed_chat_ids)} Dokumenten"
            )
            return fair_candidates[: limit * 2], query_vector

        # =======================================================================
        # GLOBALE SUCHE (Standard-Modus)
        # =======================================================================
        where_filter = None
        if allowed_chat_ids:
            where_filter = {"chat_id": {"$in": allowed_chat_ids}}
        if filter_role:
            role_filter = {"role": {"$contains": filter_role.lower()}}
            where_filter = (
                {"$and": [where_filter, role_filter]} if where_filter else role_filter
            )

        query_kwargs = dict(
            query_embeddings=[query_vector],
            n_results=min(limit * 2, collection.count() or 1),
            include=["documents", "metadatas", "distances", "embeddings"],
        )
        if where_filter:
            query_kwargs["where"] = where_filter

        results = collection.query(**query_kwargs)

        cleaned_results = []
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 1.0

            # Metadata anreichern (Fallback für alte Einträge)
            chat_title = meta.get("chat_title", "")
            if chat_title:
                changed = False
                if not meta.get("date"):
                    meta["date"] = extract_date_from_chat_title(chat_title)
                    changed = True
                if not meta.get("version"):
                    spk = (
                        meta.get("model_name")
                        or meta.get("speaker")
                        or meta.get("role")
                    )
                    meta["version"] = extract_version_from_chat_title(chat_title, spk)
                    changed = True

            embedding = None
            # Phase 6.5 Fix: NumPy Array Truth-Value Error vermeiden!
            _embs = results.get("embeddings")
            if _embs is not None and len(_embs) > 0 and _embs[0] is not None:
                embedding = _embs[0][i] if i < len(_embs[0]) else None

            data = {
                "vector_doc_id": doc_id,
                "content": results["documents"][0][i] if results["documents"] else "",
                "metadata": meta,
                "chat_id": meta.get("chat_id", ""),
                "embedding": embedding,
                # ChromaDB Cosine Distance → Score (1 - distance)
                "score": float(1.0 - distance),
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
        allowed_chat_ids: List[str] = None,
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
            allowed_chat_ids=allowed_chat_ids,
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
                tokenized_query, list(doc_map.keys()), n=2000
            )

            for idx in top_n_indices:
                doc_data = doc_map[idx]

                if allowed_chat_ids and doc_data.get("chat_id") not in allowed_chat_ids:
                    continue

                if (
                    filter_role
                    and filter_role.lower()
                    not in doc_data.get("metadata", {}).get("role", "").lower()
                ):
                    continue

                bm25_candidates.append(doc_data)

                if len(bm25_candidates) >= limit * 3:
                    break

            logger.info(f"📚 BM25-Suche: {len(bm25_candidates)} Treffer.")

        # 3. RRF-Fusion
        rrf_scores = {}

        def add_scores(candidates, weight=1.0):
            for rank, doc in enumerate(candidates):
                doc_id = doc.get("vector_doc_id")
                if not doc_id:
                    continue
                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = {"doc": doc, "score": 0.0}
                rrf_scores[doc_id]["score"] += weight * (1 / (RRF_K + rank + 1))

        add_scores(vector_candidates)
        add_scores(bm25_candidates)

        sorted_results = sorted(
            rrf_scores.values(), key=lambda x: x["score"], reverse=True
        )

        # ======================================================================
        # VIP-SCHUTZ (unverändert v50.3)
        # ======================================================================
        final_results = []

        if allowed_chat_ids and len(allowed_chat_ids) <= 10:
            results_by_chat = {cid: [] for cid in allowed_chat_ids}

            for item in sorted_results:
                doc = item["doc"]
                cid = doc.get("chat_id")
                if cid in results_by_chat:
                    results_by_chat[cid].append(doc)

            vip_set = set()
            for cid, docs in results_by_chat.items():
                for d in docs[:3]:
                    uid = d.get("vector_doc_id")
                    if uid and uid not in vip_set:
                        final_results.append(d)
                        vip_set.add(uid)

            logger.info(f"🛡️ VIP-Schutz: {len(final_results)} Chunks garantiert.")

            for item in sorted_results:
                doc = item["doc"]
                uid = doc.get("vector_doc_id")
                if len(final_results) >= limit:
                    break
                if uid and uid not in vip_set:
                    final_results.append(doc)
                    vip_set.add(uid)
        else:
            final_results = [item["doc"] for item in sorted_results[:limit]]

        for res in final_results:
            res["_rrf_active"] = True

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
        keyword_weight: float = 0.3,
    ) -> Tuple[List[Dict], Any]:
        """Legacy-Wrapper. Unverändert."""
        return self.hybrid_search_rrf(query, limit, filter_role, allowed_chat_ids)
