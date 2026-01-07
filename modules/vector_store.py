# modules/vector_store.py - v50.7: AUDIT-FIX (Thread-Safety + Cleanup)
"""
Firestore Vector Store - Zentrales Interface für Vektor-Suche und RRF.

PHILOSOPHIE:
Verwaltet Embeddings, Chunking und hybride Suche (Semantic + BM25).
Kernkomponente der Hermeneutic Reconstruction Engine.

NEU v50.7 (AUDIT-FIXES):
1. Thread-Safe BM25-Cache (kritisch für Multi-User Deployment!)
2. Tote Imports entfernt (EMBEDDING_DIMENSIONS)
3. Redundante Definitionen entfernt (lokales EMBEDDING_MODEL)
4. Tote Variable entfernt (_BM25_LAST_UPDATE)
5. Fehlende Warnungen bei Import-Fehlern
6. Verbesserte Docstrings & Type Hints
7. Konsistentes Logging

ÄNDERUNGSHISTORIE:
- v50.7: Vollständige Überarbeitung (Audit)
- v50.3: RRF mit VIP-Schutz
- v50.2: Investigativ-Modus mit Fairness-Quota
- v50.1: RRF, Multilinguale Query-Expansion
- v49: Initiale Version
"""

import os
import logging
import time
import uuid
import re
import threading
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
import google.generativeai as genai

# Config Import (v50.7: Keine redundanten Definitionen mehr!)
from modules.config import EMBEDDING_MODEL

# Firestore
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

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
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konstanten
COLLECTION_NAME = "embeddings"
RRF_K = 60  # Reciprocal Rank Fusion Konstante

# API Key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


# ==============================================================================
# THREAD-SAFE BM25-CACHE (NEU v50.7)
# ==============================================================================
class BM25Cache:
    """
    Thread-safe Singleton für BM25-Index.
    
    PROBLEM (v50.6):
    Globale Variablen (_BM25_INDEX, _BM25_DOC_MAP) waren nicht thread-safe.
    In Multi-User-Umgebungen konnten Race Conditions auftreten.
    
    LÖSUNG (v50.7):
    Singleton-Pattern mit threading.Lock für sichere Concurrent Access.
    
    VERWENDUNG:
        cache = BM25Cache()
        index, doc_map = cache.get_index()
        if index is None:
            # Build index...
            cache.set_index(new_index, new_doc_map)
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton-Pattern: Nur eine Instanz pro Prozess."""
        if cls._instance is None:
            with cls._lock:
                # Double-Checked Locking
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.index = None
                    cls._instance.doc_map = None
                    cls._instance.last_build_time = 0
        return cls._instance
    
    def get_index(self) -> Tuple[Optional[Any], Optional[Dict]]:
        """
        Thread-safe Abruf des BM25-Index.
        
        Returns:
            Tuple: (BM25Okapi-Index oder None, Doc-Map oder None)
        """
        with self._lock:
            return self.index, self.doc_map
    
    def set_index(self, index, doc_map):
        """
        Thread-safe Update des BM25-Index.
        
        Args:
            index: BM25Okapi-Instanz
            doc_map: Dict mit Dokument-Metadaten
        """
        with self._lock:
            self.index = index
            self.doc_map = doc_map
            self.last_build_time = time.time()
            logger.info(f"🔄 BM25-Cache aktualisiert. Docs: {len(doc_map)}")
    
    def invalidate(self):
        """
        Löscht den Cache (z.B. nach neuem Import).
        
        WICHTIG: Muss aufgerufen werden nach process_and_store_chat()!
        """
        with self._lock:
            self.index = None
            self.doc_map = None
            self.last_build_time = 0
            logger.info("🗑️ BM25-Cache invalidiert.")


# ==============================================================================
# FIRESTORE VECTOR STORE
# ==============================================================================
class FirestoreVectorStore:
    """
    Interface für Firestore Vector Search + BM25 Hybrid Retrieval.
    
    HAUPTFUNKTIONEN:
    - chunk_text(): Intelligentes Text-Chunking mit Speaker-Detection
    - process_and_store_chat(): Import & Vektorisierung von Chats
    - semantic_search(): Pure Vektor-Suche (Cosine Similarity)
    - hybrid_search_rrf(): Hybrid-Suche (Semantic + BM25 mit RRF-Fusion)
    
    THREADING:
    Ab v50.7 ist der BM25-Cache thread-safe. Alle anderen Methoden sind
    stateless und damit implizit thread-safe.
    """
    
    def __init__(self, db_client: firestore.Client):
        """
        Initialisiert den Vector Store.
        
        Args:
            db_client: Firestore Client-Instanz
        """
        self.db = db_client
    
    # ==========================================================================
    # EMBEDDING & CHUNKING
    # ==========================================================================
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Holt Embedding von Gemini API mit Retry-Logic.
        
        Args:
            text: Zu vektorisierender Text
        
        Returns:
            768-dimensionaler Vektor oder None bei Fehler
        """
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
                logger.warning(
                    f"⚠️ Embedding-Fehler (Versuch {attempt+1}/{retries}): {e}"
                )
                if attempt < retries - 1:
                    time.sleep((attempt + 1) * 2)
        
        return None
    
    def chunk_text(
        self, 
        text: str, 
        max_tokens: int = 1000, 
        overlap: int = 300
    ) -> List[str]:
        """
        Intelligentes Text-Chunking mit Speaker-Context-Injection.
        
        STRATEGIE:
        1. Chunke nach Token-Limit (mit Satz-Boundaries)
        2. Detektiere Sprecher-Wechsel ("Modell: XYZ")
        3. Injiziere Kontext in Chunks ohne expliziten Sprecher
        
        Args:
            text: Vollständiger Chat-Text
            max_tokens: Max Tokens pro Chunk (~4 chars/token)
            overlap: Overlap in Tokens für Kontext-Kontinuität
        
        Returns:
            Liste von Chunk-Strings mit injiziertem Kontext
        
        Beispiel:
            Input: "Modell: Claude\nIch bin ein KI-Assistent.\n\nWeiterer Text..."
            Output: [
                "[Kontext: Sprecher ist Claude] Ich bin ein KI-Assistent.",
                "[Kontext: Sprecher ist Claude] Weiterer Text..."
            ]
        """
        if not text:
            return []
        
        chunk_size_chars = max_tokens * 4
        overlap_chars = overlap * 4
        
        # Speaker Detection (Regex für "Modell: NAME" oder "**Modell**: NAME")
        speaker_pattern = re.compile(
            r"(?:\*\*|#)?\s*Modell:?\s*(.*?)(?:\*\*|$|\n)", 
            re.IGNORECASE
        )
        speaker_matches = list(speaker_pattern.finditer(text))
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size_chars
            
            # Satz-Boundary suchen (verhindert Cut-Off mitten im Satz)
            if end < len(text):
                last_period = text.rfind('.', start, end)
                if last_period != -1 and last_period > start + (chunk_size_chars // 2):
                    end = last_period + 1
            
            raw_chunk = text[start:end]
            
            # Kontext-Injektion: Finde letzten Sprecher VOR diesem Chunk
            current_speaker = None
            for match in speaker_matches:
                if match.start() < end:
                    current_speaker = match.group(1).strip()
                else:
                    break  # Matches sind chronologisch sortiert
            
            # Füge Kontext hinzu, falls Chunk selbst keinen Sprecher erwähnt
            final_chunk = raw_chunk
            if current_speaker and f"Modell: {current_speaker}" not in raw_chunk[:50]:
                final_chunk = f"[Kontext: Sprecher ist {current_speaker}] {raw_chunk}"
            
            chunks.append(final_chunk)
            
            # Overlap für nächsten Chunk
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
        Importiert Chat-Nachrichten und speichert Embeddings in Firestore.
        
        WORKFLOW:
        1. Invalidiere BM25-Cache (alte Daten werden ungültig)
        2. Lösche alte Embeddings für diesen Chat (falls Reimport)
        3. Chunke jede Nachricht
        4. Erzeuge Embeddings
        5. Extrahiere Metadaten (Datum, Version, etc.)
        6. Klassifiziere Chunks (optional, falls ChunkClassifier verfügbar)
        7. Speichere in Firestore mit Batch-Writes (max 400 Ops/Batch)
        
        Args:
            chat_id: Eindeutige Chat-ID
            messages: Liste von Message-Dicts mit 'content', 'role', etc.
            custom_metadata: Zusätzliche Metadaten (z.B. 'chat_title')
        
        Returns:
            Tuple: (Anzahl gespeicherter Chunks, Anzahl übersprungener Chunks)
        
        PERFORMANCE:
        - ~2-5 Chunks/Sekunde (API-limitiert)
        - Batch-Writes reduzieren DB-Calls um ~80%
        """
        logger.info(f"🔄 Starte Vektorisierung für Chat {chat_id}...")
        
        # 1. Cache invalidieren (WICHTIG!)
        cache = BM25Cache()
        cache.invalidate()
        
        # 2. Alte Vektoren löschen
        self.delete_chat_embeddings(chat_id)
        
        # 3. Batch-Setup
        batch = self.db.batch()
        op_count = 0
        total_chunks = 0
        
        if custom_metadata is None:
            custom_metadata = {}
        
        # 4. ChunkClassifier initialisieren (optional)
        classifier = ChunkClassifier() if ChunkClassifier else None
        
        # 5. Nachrichten verarbeiten
        for msg in messages:
            content = msg.get('content', '')
            role = msg.get('role') or msg.get('author') or 'unknown'
            msg_id = msg.get('id', str(uuid.uuid4()))
            
            # Skip leere Nachrichten
            if not content or len(content.strip()) < 50:
                continue
            
            # Chunking
            chunks = self.chunk_text(content)
            
            for i, chunk_text in enumerate(chunks):
                # Embedding erzeugen
                vec = self._get_embedding(chunk_text)
                if not vec:
                    logger.warning(f"⚠️ Chunk {i} von Nachricht {msg_id}: Embedding fehlgeschlagen.")
                    continue
                
                # Dokument-ID
                doc_id = f"{chat_id}_{msg_id}_{i}"
                doc_ref = self.db.collection(COLLECTION_NAME).document(doc_id)
                
                # Metadaten aufbauen
                meta = {
                    "role": role, 
                    "source_length": len(content)
                }
                meta.update(custom_metadata)
                
                # Metadata Extraction (Datum, Version)
                chat_title = meta.get('chat_title', '')
                speaker_hint = meta.get('speaker') or meta.get('model') or role
                
                if chat_title:
                    if 'date' not in meta or not meta['date']:
                        meta['date'] = extract_date_from_chat_title(chat_title)
                    
                    if 'version' not in meta or not meta['version']:
                        meta['version'] = extract_version_from_chat_title(
                            chat_title, 
                            speaker_hint
                        )
                
                # Chunk-Klassifikation (optional)
                if classifier:
                    meta = classifier.process_chunk(chunk_text, meta)
                
                # Firestore-Dokument
                data = {
                    "chat_id": chat_id,
                    "message_id": msg_id,
                    "chunk_index": i,
                    "content": chunk_text,
                    "embedding": Vector(vec),
                    "metadata": meta,
                    "created_at": firestore.SERVER_TIMESTAMP
                }
                
                # Zu Batch hinzufügen
                batch.set(doc_ref, data)
                op_count += 1
                total_chunks += 1
                
                # Batch committen bei 400 Ops (Firestore Limit: 500)
                if op_count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    op_count = 0
                    time.sleep(0.5)  # Rate-Limiting
        
        # Finaler Batch-Commit
        if op_count > 0:
            batch.commit()
        
        logger.info(f"✅ Chat {chat_id}: {total_chunks} Chunks gespeichert.")
        return total_chunks, 0
    
    def delete_chat_embeddings(self, chat_id: str):
        """
        Löscht alle Embeddings für einen Chat (Hard Delete).
        
        Args:
            chat_id: Chat-ID zum Löschen
        
        WICHTIG: Invalidiert automatisch den BM25-Cache!
        """
        docs = self.db.collection(COLLECTION_NAME).where(
            "chat_id", "==", chat_id
        ).stream()
        
        for doc in docs:
            doc.reference.delete()
        
        # Cache invalidieren
        cache = BM25Cache()
        cache.invalidate()
        
        logger.info(f"🗑️ Embeddings für Chat {chat_id} gelöscht.")
    
    # ==========================================================================
    # BM25 INDEX MANAGEMENT
    # ==========================================================================
    
    def _ensure_bm25_index(self):
        """
        Baut BM25-Index auf, falls noch nicht vorhanden (Lazy Loading).
        
        STRATEGIE:
        1. Prüfe ob Index im Cache existiert
        2. Falls nein: Lade alle Dokumente aus Firestore
        3. Tokenisiere Content (simple .split())
        4. Baue BM25Okapi-Index
        5. Speichere in Thread-Safe Cache
        
        PERFORMANCE:
        - Erster Aufruf: ~5-30 Sekunden (je nach Korpus-Größe)
        - Folge-Aufrufe: <1ms (Cache-Hit)
        
        THREAD-SAFETY:
        Vollständig thread-safe durch BM25Cache-Lock.
        """
        cache = BM25Cache()
        index, doc_map = cache.get_index()
        
        # Cache-Hit: Index existiert bereits
        if index is not None:
            return
        
        # Fallback: BM25 nicht verfügbar
        if not BM25_AVAILABLE:
            logger.debug("📚 BM25 nicht verfügbar (Library fehlt).")
            return
        
        logger.info("🏗️ Baue BM25-Index auf...")
        start = time.time()
        
        # Alle Dokumente aus Firestore laden (nur Content + Metadata)
        docs = self.db.collection(COLLECTION_NAME).select(
            ['content', 'metadata', 'chat_id']
        ).stream()
        
        corpus = []
        doc_map = {}
        count = 0
        
        for doc in docs:
            d = doc.to_dict()
            d['vector_doc_id'] = doc.id
            
            # Tokenisiere Content (Simple Whitespace Split)
            # TODO v51: Nutze besseren Tokenizer (z.B. NLTK, spaCy)
            corpus.append(d.get('content', '').lower().split())
            doc_map[count] = d
            count += 1
        
        # BM25-Index bauen
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
        """
        Berechnet Cosine Similarity zwischen zwei Numpy Arrays.
        
        Args:
            vec_a: Erster Vektor
            vec_b: Zweiter Vektor
        
        Returns:
            Similarity-Score (0.0 - 1.0)
        """
        return np.dot(vec_a, vec_b) / (
            np.linalg.norm(vec_a) * np.linalg.norm(vec_b)
        )
    
    def _get_chat_title(self, chat_id: str) -> str:
        """
        Holt Chat-Titel aus Firestore (mit Fallback).
        
        Args:
            chat_id: Chat-ID
        
        Returns:
            Titel oder "Doc {ID}" bei Fehler
        """
        try:
            chat_doc = self.db.collection('chats').document(chat_id).get()
            if chat_doc.exists:
                return chat_doc.to_dict().get('title', f'Doc {chat_id[-8:]}')
            else:
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
        Pure Vektor-Suche via Firestore Vector Search.
        
        STRATEGIE:
        - Bei ≤5 ausgewählten Docs: INVESTIGATIV-MODUS (Fairness-Quota)
        - Sonst: GLOBALE SUCHE (Best-Match über alle Docs)
        
        INVESTIGATIV-MODUS (v50.2):
        Verhindert, dass ein Dokument alle Top-Slots belegt.
        Garantiert faire Repräsentation aller ausgewählten Docs.
        
        Args:
            query: Suchquery (natürlichsprachig)
            limit: Max Ergebnisse (wird in Investigativ-Modus überschrieben)
            filter_role: Nur Chunks von diesem Role (optional)
            allowed_chat_ids: Nur Chunks aus diesen Chats (optional)
        
        Returns:
            Tuple: (Liste von Result-Dicts, Query-Vektor)
        
        Result-Dict enthält:
            - content: Chunk-Text
            - score: Cosine Similarity (0-1)
            - metadata: Chat-Titel, Datum, Version, etc.
            - chat_id: Quell-Chat
        """
        query_vector = self._get_embedding(query)
        if not query_vector:
            logger.error("❌ Konnte Query-Embedding nicht erzeugen.")
            return [], None
        
        # ======================================================================
        # INVESTIGATIV-MODUS (Fairness-Quota für ausgewählte Docs)
        # ======================================================================
        if allowed_chat_ids and len(allowed_chat_ids) <= 5:
            logger.info(
                f"🕵️‍♂️ Investigativ-Modus: {len(allowed_chat_ids)} Dokumente..."
            )
            
            docs_by_chat = {cid: [] for cid in allowed_chat_ids}
            
            # Alle Chunks aus den ausgewählten Chats laden
            docs = self.db.collection(COLLECTION_NAME).where(
                "chat_id", "in", allowed_chat_ids
            ).stream()
            
            q_vec_np = np.array(query_vector)
            
            for doc in docs:
                data = doc.to_dict()
                
                # Role-Filter
                if filter_role and filter_role.lower() not in data.get(
                    'metadata', {}
                ).get('role', '').lower():
                    continue
                
                # Embedding extrahieren
                vec_obj = data.get('embedding')
                if not vec_obj:
                    continue
                
                try:
                    vec = np.array(list(vec_obj))
                except:
                    vec = np.array(vec_obj)
                
                # Score berechnen
                score = self._cosine_similarity(q_vec_np, vec)
                
                data['vector_doc_id'] = doc.id
                data['score'] = float(score)
                
                # Zu passendem Chat hinzufügen
                cid = data.get('chat_id')
                if cid in docs_by_chat:
                    docs_by_chat[cid].append(data)
            
            # FAIRNESS-QUOTA: Gleiche Anzahl Chunks pro Doc
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
                
                # Sortiere Chunks nach Score
                chunks.sort(key=lambda x: x['score'], reverse=True)
                
                # Nimm Top N
                selected_count = min(len(chunks), quota_per_doc)
                fair_candidates.extend(chunks[:selected_count])
                
                # Logging
                chat_title = self._get_chat_title(cid)
                avg_score = sum(
                    c['score'] for c in chunks[:selected_count]
                ) / selected_count
                logger.info(
                    f"  📄 {chat_title}: {len(chunks)} total → "
                    f"{selected_count} selected (Ø Score: {avg_score:.2f})"
                )
            
            # Sortiere final nach Score
            fair_candidates.sort(key=lambda x: x['score'], reverse=True)
            
            logger.info(
                f"✅ Fairness-Quota angewendet: {len(fair_candidates)} Chunks "
                f"aus {len(allowed_chat_ids)} Dokumenten"
            )
            
            return fair_candidates[:limit * 2], query_vector
        
        # ======================================================================
        # GLOBALE SUCHE (Standard-Modus)
        # ======================================================================
        else:
            collection_ref = self.db.collection(COLLECTION_NAME)
            
            # Firestore Vector Query
            fetch_limit = 1000  # Hohe Grenze für gute Ergebnisse
            vector_query = collection_ref.find_nearest(
                vector_field="embedding",
                query_vector=Vector(query_vector),
                distance_measure=DistanceMeasure.COSINE,
                limit=fetch_limit
            )
            
            results = vector_query.get()
            
            # Ergebnisse filtern & bereinigen
            cleaned_results = []
            for doc in results:
                data = doc.to_dict()
                
                # Chat-Filter
                if allowed_chat_ids and data.get('chat_id') not in allowed_chat_ids:
                    continue
                
                # Role-Filter
                if filter_role and filter_role.lower() not in data.get(
                    'metadata', {}
                ).get('role', '').lower():
                    continue
                
                # Metadata anreichern (Fallback für alte Einträge ohne Datum/Version)
                meta = data.get('metadata', {})
                if 'chat_title' in meta:
                    changed = False
                    
                    if not meta.get('date'):
                        meta['date'] = extract_date_from_chat_title(
                            meta['chat_title']
                        )
                        changed = True
                    
                    if not meta.get('version'):
                        spk = meta.get('model_name') or meta.get('speaker') or meta.get('role')
                        meta['version'] = extract_version_from_chat_title(
                            meta['chat_title'], 
                            spk
                        )
                        changed = True
                    
                    if changed:
                        data['metadata'] = meta
                
                data['vector_doc_id'] = doc.id
                cleaned_results.append(data)
                
                # Early Exit wenn genug Ergebnisse
                if len(cleaned_results) >= limit * 2:
                    break
            
            return cleaned_results, query_vector
    
    # ==========================================================================
    # HYBRID SEARCH (RRF)
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
        
        WORKFLOW:
        1. Semantic Search (Vektor-Ähnlichkeit)
        2. BM25 Search (Keyword-Matching)
        3. RRF-Fusion (kombiniert Rankings)
        4. VIP-Schutz (garantiert Mind. 3 Chunks pro ausgewähltem Doc)
        
        RRF-FORMEL:
            score = Σ (1 / (k + rank_i))
            wobei k=60 (Standard-Wert aus Literatur)
        
        VIP-SCHUTZ (v50.3):
        Bei ≤10 ausgewählten Docs wird garantiert, dass JEDES Dokument
        mit mindestens 3 Chunks in den Ergebnissen vertreten ist,
        bevor der Rest nach Score aufgefüllt wird.
        
        RATIONALE:
        Verhindert, dass bei Vergleichsanalysen ein Dokument "totgeschwiegen"
        wird, nur weil seine Chunks minimal schlechtere Scores haben.
        
        Args:
            query: Suchquery
            limit: Max Ergebnisse (ohne VIP-Schutz)
            filter_role: Role-Filter
            allowed_chat_ids: Chat-Filter
        
        Returns:
            Tuple: (Liste von Result-Dicts mit '_rrf_active' Flag, Query-Vektor)
        """
        # 1. Vektor-Suche
        vector_candidates, query_vector = self.semantic_search(
            query, 
            limit=limit * 3,  # Mehr Kandidaten für bessere RRF-Fusion
            filter_role=filter_role, 
            allowed_chat_ids=allowed_chat_ids
        )
        
        # Fallback: BM25 nicht verfügbar
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
                n=2000  # Großer Pool für gute RRF-Fusion
            )
            
            for idx in top_n_indices:
                doc_data = doc_map[idx]
                
                # Filter anwenden
                if allowed_chat_ids and doc_data.get('chat_id') not in allowed_chat_ids:
                    continue
                
                if filter_role and filter_role.lower() not in doc_data.get(
                    'metadata', {}
                ).get('role', '').lower():
                    continue
                
                bm25_candidates.append(doc_data)
                
                if len(bm25_candidates) >= limit * 3:
                    break
            
            logger.info(f"📚 BM25-Suche: {len(bm25_candidates)} Treffer.")
        
        # 3. RRF-Fusion
        rrf_scores = {}
        
        def add_scores(candidates, weight=1.0):
            """Fügt RRF-Scores hinzu."""
            for rank, doc in enumerate(candidates):
                doc_id = doc.get('vector_doc_id')
                if not doc_id:
                    continue
                
                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = {"doc": doc, "score": 0.0}
                
                # RRF-Formel: 1 / (k + rank + 1)
                rrf_scores[doc_id]["score"] += weight * (1 / (RRF_K + rank + 1))
        
        add_scores(vector_candidates)
        add_scores(bm25_candidates)
        
        # Sortiere nach RRF-Score
        sorted_results = sorted(
            rrf_scores.values(), 
            key=lambda x: x['score'], 
            reverse=True
        )
        
        # ======================================================================
        # VIP-SCHUTZ (NEU v50.3)
        # ======================================================================
        final_results = []
        
        if allowed_chat_ids and len(allowed_chat_ids) <= 10:
            # Gruppiere nach Chat-ID
            results_by_chat = {cid: [] for cid in allowed_chat_ids}
            
            for item in sorted_results:
                doc = item['doc']
                cid = doc.get('chat_id')
                if cid in results_by_chat:
                    results_by_chat[cid].append(doc)
            
            # 1. VIP-Runde: Mind. 3 Chunks pro Dokument
            vip_set = set()  # Tracking, welche Docs schon drin sind
            
            for cid, docs in results_by_chat.items():
                top_3 = docs[:3]  # Erste 3 sind automatisch VIP
                
                for d in top_3:
                    uid = d.get('vector_doc_id')
                    if uid and uid not in vip_set:
                        final_results.append(d)
                        vip_set.add(uid)
            
            logger.info(
                f"🛡️ VIP-Schutz: {len(final_results)} Chunks garantiert aufgenommen."
            )
            
            # 2. Auffüll-Runde: Rest nach Score
            for item in sorted_results:
                doc = item['doc']
                uid = doc.get('vector_doc_id')
                
                if len(final_results) >= limit:
                    break
                
                if uid and uid not in vip_set:
                    final_results.append(doc)
                    vip_set.add(uid)
        
        else:
            # Standard: Keine VIP-Behandlung
            final_results = [item['doc'] for item in sorted_results[:limit]]
        
        # Flag setzen (für Logging/Debugging)
        for res in final_results:
            res['_rrf_active'] = True
        
        logger.info(f"⚖️ RRF Fusion: {len(final_results)} finale Treffer.")
        
        return final_results, query_vector
    
    # ==========================================================================
    # CACHE MANAGEMENT (PUBLIC API)
    # ==========================================================================
    
    def invalidate_bm25_cache(self):
        """
        Invalidiert den BM25-Cache manuell (Public API für Admin-Tools).
        
        USE CASES:
        - Nach Bulk-Metadata-Updates (ohne Reindizierung)
        - Nach manuellem Löschen von Embeddings via Firestore-Console
        - Für Admin-Tools, die Metadata ändern (z.B. vector_admin.py)
        
        WICHTIG: 
        Diese Methode löscht NUR den Cache, NICHT die Vektoren in Firestore!
        Nach Metadata-Änderungen MUSS trotzdem neu indiziert werden,
        damit die neuen Labels auch in den Embeddings erscheinen.
        
        RATIONALE:
        Ohne Cache-Invalidierung würde BM25-Suche alte Labels zurückgeben,
        was zu Inkonsistenzen zwischen Firestore-Metadata und Cache führt.
        
        Beispiel:
            >>> # User ändert Label via Admin-UI (nur Metadata!)
            >>> update_chat_metadata(chat_id, model_name="Claude")
            >>> 
            >>> # Cache invalidieren (sonst zeigt BM25 alte Labels)
            >>> vector_store = FirestoreVectorStore(db)
            >>> vector_store.invalidate_bm25_cache()
            >>> 
            >>> # Später: Neu indizieren für korrekte Labels in Embeddings
            >>> messages = get_raw_chat_messages(chat_id)
            >>> vector_store.process_and_store_chat(chat_id, messages, meta)
        
        Returns:
            None
        """
        cache = BM25Cache()
        cache.invalidate()
        logger.info("🗑️ BM25-Cache manuell invalidiert (Public API).")
    
    # ==========================================================================
    # LEGACY WRAPPER
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
        """
        Legacy-Wrapper für alte API-Kompatibilität.
        
        DEPRECATED: Nutze stattdessen hybrid_search_rrf().
        
        Die Parameter 'keywords' und 'keyword_weight' werden ignoriert,
        da RRF diese obsolet macht.
        """
        return self.hybrid_search_rrf(query, limit, filter_role, allowed_chat_ids)