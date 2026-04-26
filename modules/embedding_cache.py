# modules/embedding_cache.py
import hashlib
import struct
import sqlite3
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class EmbeddingCache:
    """Cacht Embeddings in SQLite, um redundante API-Aufrufe zu vermeiden."""
    
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    @staticmethod
    def _hash_text(text: str) -> str:
        """Erstellt einen SHA-256 Hash des Textes."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    @staticmethod
    def _serialize_embedding(embedding: List[float]) -> bytes:
        """Konvertiert eine Liste von Floats in einen kompakten BLOB (struct)."""
        # 'f' steht für 4-Byte Float. Schneller und sicherer als pickle.
        return struct.pack(f'{len(embedding)}f', *embedding)

    @staticmethod
    def _deserialize_embedding(blob: bytes) -> List[float]:
        """Konvertiert einen BLOB zurück in eine Liste von Floats."""
        # Berechne Anzahl der Floats anhand der BLOB-Länge
        count = len(blob) // struct.calcsize('f')
        return list(struct.unpack(f'{count}f', blob))

    def get(self, text: str) -> Optional[List[float]]:
        """Sucht nach dem Embedding im Cache. Gibt None zurück bei Cache-Miss."""
        text_hash = self._hash_text(text)
        try:
            row = self.db.execute(
                "SELECT embedding FROM embedding_cache WHERE text_hash = ?", 
                (text_hash,)
            ).fetchone()
            if row:
                return self._deserialize_embedding(row[0])
        except Exception as e:
            logger.warning(f"⚠️ Cache-Lesefehler (hash={text_hash[:8]}...): {e}")
        return None

    def set(self, text: str, embedding: List[float]) -> None:
        """Speichert ein Embedding im Cache (ohne Commit!)."""
        text_hash = self._hash_text(text)
        blob = self._serialize_embedding(embedding)
        try:
            self.db.execute(
                "INSERT OR IGNORE INTO embedding_cache (text_hash, embedding) VALUES (?, ?)",
                (text_hash, blob)
            )
        except Exception as e:
            # WICHTIG: Rollback, um die SQLite-Verbindung nicht zu vergiften!
            try:
                self.db.rollback()
            except Exception:
                pass
            logger.warning(f"⚠️ Cache-Schreibfehler (hash={text_hash[:8]}...): {e}")