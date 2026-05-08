# modules/database.py — v52: SQLite + LM Studio
"""
Datenbankschicht der Hermeneutic Reconstruction Engine.

MIGRATION v52:
- Firestore-Namen bereinigt (Phase 2.3)
- get_firestore_client() → get_db_connection()
- create_chat_in_firestore() → create_chat()

ÖFFENTLICHE API:
- get_db_connection()              DB-Verbindung (Singleton)
- create_chat()                    Chat anlegen
- save_message()                   Nachricht speichern
- delete_chat()                    Chat + Embeddings löschen
- rename_chat()                    Chat umbenennen
- get_chat_list()                  Chat-Liste laden
- load_chat_history()              Chat-Historie laden
- generate_and_update_title()      KI-Titel generieren
- load_global_settings()           Settings laden
- save_global_settings()           Settings speichern
- get_all_chats_metadata()         Admin: alle Chats
- update_chat_metadata()           Admin: Metadaten ändern
- get_raw_chat_messages()          Admin: Rohdaten für Re-Indizierung
"""

import sqlite3
import json
import uuid
import logging
import atexit
import threading
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from modules.config import SQLITE_PATH, get_llm_client
from modules.config import get_system_message

logger = logging.getLogger(__name__)

# Streamlit optional — database.py funktioniert auch ohne laufende ST-Session
try:
    import streamlit as st

    _STREAMLIT_AVAILABLE = True
except ImportError:
    _STREAMLIT_AVAILABLE = False


def _st_error(msg: str):
    """Zeigt Fehler in Streamlit oder fällt auf Logging zurück."""
    logger.error(msg)
    if _STREAMLIT_AVAILABLE:
        try:
            st.error(msg)
        except Exception:
            pass  # Außerhalb einer ST-Session — kein Problem


# ==============================================================================
# DATENBANKSCHEMA
# ==============================================================================
_SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT 'Neuer Chat',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    last_updated TEXT NOT NULL DEFAULT (datetime('now')),
    model_name  TEXT,
    metadata    TEXT,
    skipped_chunks INTEGER DEFAULT 0,
    chunk_count   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    chat_id     TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    metadata    TEXT,
    FOREIGN KEY (chat_id) REFERENCES chats(id)
);

CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_id
    ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp
    ON messages(chat_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_chats_updated
    ON chats(last_updated DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    chat_id UNINDEXED,
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS messages_ai
AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content, chat_id)
    VALUES (new.rowid, new.content, new.chat_id);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad
AFTER DELETE ON messages BEGIN
    DELETE FROM messages_fts WHERE rowid = old.rowid;
END;

-- FTS5 Titel-Suche (A.16)
CREATE VIRTUAL TABLE IF NOT EXISTS chats_fts USING fts5(
    title,
    content='chats',
    content_rowid='rowid',
    tokenize='unicode61'
);

CREATE TRIGGER IF NOT EXISTS chats_ai
AFTER INSERT ON chats BEGIN
    INSERT INTO chats_fts(rowid, title) VALUES (new.rowid, new.title);
END;

CREATE TRIGGER IF NOT EXISTS chats_au
AFTER UPDATE OF title ON chats BEGIN
    UPDATE chats_fts SET title = new.title WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS chats_ad
AFTER DELETE ON chats BEGIN
    DELETE FROM chats_fts WHERE rowid = old.rowid;
END;

-- Phase 4.4: Embedding Cache
CREATE TABLE IF NOT EXISTS embedding_cache (
    text_hash TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Phase A.3: Analysis Persistenz
CREATE TABLE IF NOT EXISTS analyses (
    analysis_id       TEXT PRIMARY KEY,
    timestamp         TEXT NOT NULL DEFAULT (datetime('now')),
    query             TEXT NOT NULL,
    intent            TEXT,
    semantic_intent   TEXT,
    analysis_domain   TEXT DEFAULT 'analysis_pipeline',
    model             TEXT,
    temperature       REAL,
    seed              INTEGER,
    top_p             REAL,
    cited_document_ids TEXT,  -- JSON-Array
    answer_text       TEXT
);
CREATE INDEX IF NOT EXISTS idx_analyses_timestamp
    ON analyses(timestamp DESC);

-- Phase A.7: Enforcer Human-in-the-Loop Reviews
CREATE TABLE IF NOT EXISTS enforcer_reviews (
    id                  TEXT PRIMARY KEY,
    claim_hash          TEXT NOT NULL,
    claim_text          TEXT NOT NULL,
    source_id           TEXT NOT NULL,
    source_content      TEXT NOT NULL,
    source_content_hash TEXT NOT NULL,
    enforcer_version    TEXT NOT NULL,
    enforcer_valid      INTEGER NOT NULL,
    enforcer_reason     TEXT,
    human_valid         INTEGER,                -- NULL = unreviewed, 0 = falsch, 1 = korrekt
    human_comment       TEXT,
    reviewed_at         TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_enforcer_reviews_unreviewed ON enforcer_reviews(human_valid) WHERE human_valid IS NULL;
CREATE INDEX IF NOT EXISTS idx_claim_hash ON enforcer_reviews(claim_hash);
CREATE INDEX IF NOT EXISTS idx_enforcer_version ON enforcer_reviews(enforcer_version);
CREATE UNIQUE INDEX IF NOT EXISTS idx_claim_hash_version ON enforcer_reviews(claim_hash, enforcer_version);

-- Phase 4.3: Chunk Registry (SQLite treibt, ChromaDB folgt)
CREATE TABLE IF NOT EXISTS chunk_registry (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id    TEXT UNIQUE NOT NULL,
    chat_id     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chunk_registry_chat_seq
    ON chunk_registry(chat_id, seq);

-- A.13 Deduplication: content_hash für Chunk-Deduplizierung
-- HINWEIS: Migration + Index in get_db_connection() via Python
-- (ALTER TABLE ADD COLUMN IF NOT EXISTS wird von SQLite <3.35.0 nicht unterstützt)
"""

# ==============================================================================
# SINGLETON-VERBINDUNG (Robust: Streamlit + Skripte + Migrations-Tools)
# ==============================================================================
_db_connection: Optional[sqlite3.Connection] = None
_db_lock = threading.Lock()


def _close_db():
    """Schließt die SQLite-Verbindung beim Programmende (atexit)."""
    global _db_connection
    if _db_connection is not None:
        try:
            _db_connection.close()
            logger.info("✅ SQLite-Verbindung geschlossen (atexit).")
        except Exception:
            pass
        _db_connection = None


def _db_write(func):
    """Dekorator: Sichert Schreibzugriffe mit threading.Lock."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        with _db_lock:
            return func(*args, **kwargs)

    return wrapper


def get_db_connection() -> Optional[sqlite3.Connection]:
    """
    Robuster SQLite-Singleton.
    Funktioniert in Streamlit, Migrations-Skripten und Admin-Tools gleichermaßen.
    WAL-Mode erlaubt gleichzeitige Lese-Zugriffe ohne Blocking.
    """
    global _db_connection
    if _db_connection is None:
        try:
            SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(SQLITE_PATH),
                check_same_thread=False,  # Für Multi-Thread (Streamlit)
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(_SCHEMA)
            # Live-Migration: skipped_chunks für bestehende DBs
            try:
                conn.execute(
                    "ALTER TABLE chats ADD COLUMN skipped_chunks INTEGER DEFAULT 0"
                )
                conn.commit()
                logger.info("✅ Migration: skipped_chunks Spalte hinzugefügt.")
            except Exception:
                pass  # Spalte existiert bereits — kein Problem

            # Live-Migration: content_hash für chunk_registry (A.13)
            try:
                cursor = conn.execute("PRAGMA table_info(chunk_registry)")
                columns = [row[1] for row in cursor.fetchall()]
                if "content_hash" not in columns:
                    conn.execute(
                        "ALTER TABLE chunk_registry ADD COLUMN content_hash TEXT"
                    )
                    conn.commit()
                    logger.info("✅ Migration: content_hash Spalte hinzugefügt.")
                # Index erstellen (idempotent — funktioniert auch bei vorhandener Spalte)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_chunk_registry_hash ON chunk_registry(content_hash)"
                )
                conn.commit()
            except Exception as e:
                logger.warning(f"⚠️ Migration content_hash fehlgeschlagen: {e}")

            # Live-Migration: reviewer Spalte für enforcer_reviews (A.7)
            try:
                conn.execute(
                    "ALTER TABLE enforcer_reviews ADD COLUMN reviewer TEXT"
                )
                conn.commit()
                logger.info("✅ Migration: reviewer Spalte in enforcer_reviews hinzugefügt.")
            except Exception:
                pass  # Spalte existiert bereits

            # Live-Migration: A.8 Confidence Calibration
            try:
                conn.execute(
                    "ALTER TABLE enforcer_reviews ADD COLUMN enforcer_confidence REAL DEFAULT 1.0"
                )
                conn.commit()
                logger.info("✅ Migration: enforcer_confidence Spalte in enforcer_reviews hinzugefügt.")
            except Exception:
                pass  # Spalte existiert bereits

            # Live-Migration: Phase 4.3 chunk_count in chats
            try:
                conn.execute(
                    "ALTER TABLE chats ADD COLUMN chunk_count INTEGER DEFAULT 0"
                )
                conn.commit()
                logger.info("✅ Migration: chunk_count Spalte in chats hinzugefügt.")
            except Exception:
                pass  # Spalte existiert bereits

            # Live-Migration: FTS5 Delete-Trigger reparieren (Phase 4.4 Fix)
            try:
                conn.execute("DROP TRIGGER IF EXISTS messages_ad")
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS messages_ad
                    AFTER DELETE ON messages BEGIN
                        DELETE FROM messages_fts WHERE rowid = old.rowid;
                    END
                """)
                conn.commit()
                logger.info("✅ Migration: FTS5 Delete-Trigger repariert.")
            except Exception as e:
                logger.warning(f"⚠️ Migration FTS5 Trigger fehlgeschlagen: {e}")

            # Live-Migration: chats_fts für Titel-Suche (A.16)
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS chats_fts USING fts5(
                        title,
                        content='chats',
                        content_rowid='rowid',
                        tokenize='unicode61'
                    )
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS chats_ai
                    AFTER INSERT ON chats BEGIN
                        INSERT INTO chats_fts(rowid, title) VALUES (new.rowid, new.title);
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS chats_au
                    AFTER UPDATE OF title ON chats BEGIN
                        UPDATE chats_fts SET title = new.title WHERE rowid = old.rowid;
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS chats_ad
                    AFTER DELETE ON chats BEGIN
                        DELETE FROM chats_fts WHERE rowid = old.rowid;
                    END
                """)
                conn.commit()
                logger.info("✅ Migration: chats_fts Titel-Suche erstellt.")
            except Exception as e:
                logger.warning(f"⚠️ Migration chats_fts fehlgeschlagen: {e}")
            conn.commit()
            _db_connection = conn
            atexit.register(_close_db)
            logger.info(f"✅ SQLite verbunden: {SQLITE_PATH}")
        except Exception as e:
            logger.error(f"❌ SQLite-Verbindungsfehler: {e}")
            _st_error(f"🔥 Datenbankfehler: {e}")
            return None
    return _db_connection


def get_db():
    """Alias für get_db_connection() — Kurzname."""
    return get_db_connection()


# ==============================================================================
# 2. CHAT-MANAGEMENT
# ==============================================================================


@_db_write
def create_chat(title: str = "Neuer Chat") -> Optional[str]:
    """Erstellt einen neuen Chat. Gibt chat_id zurück."""
    db = get_db_connection()
    if db is None:
        return None
    try:
        chat_id = str(uuid.uuid4())
        db.execute("""INSERT INTO chats (id, title) VALUES (?, ?)""", (chat_id, title))
        db.commit()
        logger.info(f"✅ Chat erstellt: ID={chat_id}, Title={title}")
        return chat_id
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen des Chats: {e}")
        _st_error(f"❌ Fehler beim Erstellen des Chats: {e}")
        return None


@_db_write
def save_message(
    chat_id: str, role: str, content: str, metadata: Optional[Dict] = None
) -> bool:
    """
    Speichert eine Nachricht.
    Identische Signatur inkl. metadata-Support.
    """
    db = get_db_connection()
    if not db or not chat_id:
        return False
    try:
        msg_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        db.execute(
            """INSERT INTO messages (id, chat_id, role, content, timestamp, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                msg_id,
                chat_id,
                role,
                content,
                now,
                json.dumps(metadata) if metadata else None,
            ),
        )
        db.execute("""UPDATE chats SET last_updated = ? WHERE id = ?""", (now, chat_id))
        db.commit()
        return msg_id  # Phase 6.5: ID zurückgeben für Editor-Logik
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern der Nachricht: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None

@_db_write
def delete_chat(chat_id: str) -> bool:
    """
    Löscht Chat + Nachrichten + Embeddings + Registry.
    v54.1: Defense-in-Depth — SQLite-Registry wird explizit vor ChromaDB gelöscht,
    damit Geister-Vektoren bei ChromaDB-Fehlschlag nicht zu Inkonsistenzen führen.
    """
    # --- SCHRITT 1: SQLite Registry bereinigen (schnell, zuverlässig) ---
    try:
        unregister_chat_chunks(chat_id)
    except Exception as e:
        logger.warning(f"⚠️ Registry-Löschung für Chat {chat_id[-8:]} fehlgeschlagen: {e}")

    # --- SCHRITT 2: SQL Löschung mit Auto-Retry ---
    max_retries = 2
    for attempt in range(max_retries):
        db = get_db_connection()
        if db is None:
            return False

        try:
            db.rollback()  # Poisoned State bereinigen
            db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            db.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            db.commit()
            logger.info(f"🗑️ Chat {chat_id[-8:]} inkl. SQL-Daten gelöscht.")
            break
        except sqlite3.OperationalError as e:
            logger.warning(f"⚠️ Delete Chat Versuch {attempt+1} fehlgeschlagen (OperationalError): {e}")
            try:
                db.rollback()
            except Exception:
                pass
            global _db_connection
            if _db_connection:
                try:
                    _db_connection.close()
                except Exception:
                    pass
            _db_connection = None
            if attempt == max_retries - 1:
                _st_error(f"Fehler beim Löschen des Chats (selbst nach DB-Reset): {e}")
                return False
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            _st_error(f"Unerwarteter Fehler beim Löschen des Chats: {e}")
            return False

    # --- SCHRITT 3: ChromaDB bereinigen (best-effort, async-safe) ---
    try:
        from modules.vector_store import LocalVectorStore
        vs = LocalVectorStore()
        vs.delete_chat_embeddings(chat_id)
    except Exception as e:
        logger.warning(
            f"⚠️ ChromaDB-Löschung für Chat {chat_id[-8:]} fehlgeschlagen. "
            f"Starte App neu oder nutze 'System-Health' zum Aufräumen. Fehler: {e}"
        )

    return True

# ==============================================================================
# 2.1 MESSAGE EDITING (Phase 6.5)
# ==============================================================================

@_db_write
def update_message_content(msg_id: str, new_content: str) -> bool:
    """Aktualisiert den Inhalt einer bestimmten Nachricht."""
    db = get_db_connection()
    if not db:
        return False
    try:
        db.execute("UPDATE messages SET content = ? WHERE id = ?", (new_content, msg_id))
        db.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Fehler beim Updaten der Nachricht: {e}")
        try: db.rollback()
        except: pass
        return False

@_db_write
def delete_messages_after(chat_id: str, timestamp: str) -> bool:
    """Löscht alle Nachrichten eines Chats, die NACH dem gegebenen Timestamp liegen (Zeitreise)."""
    db = get_db_connection()
    if not db:
        return False
    try:
        db.execute("DELETE FROM messages WHERE chat_id = ? AND timestamp > ?", (chat_id, timestamp))
        db.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Fehler bei Zeitreise-Löschung: {e}")
        try: db.rollback()
        except: pass
        return False

@_db_write
def delete_message_by_id(msg_id: str) -> bool:
    """Löscht eine einzelne Nachricht anhand ihrer ID."""
    db = get_db_connection()
    if not db:
        return False
    try:
        db.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
        db.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Fehler beim Löschen der Nachricht: {e}")
        try: db.rollback()
        except: pass
        return False

@_db_write
def delete_messages_by_ids(ids: list) -> bool:
    """Löscht mehrere Nachrichten anhand ihrer IDs (Turn löschen)."""
    if not ids: return True
    db = get_db_connection()
    if not db:
        return False
    try:
        placeholders = ','.join(['?'] * len(ids))
        db.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", ids)
        db.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Fehler beim Bulk-Löschen: {e}")
        try: db.rollback()
        except: pass
        return False

@_db_write
def rename_chat(chat_id: str, new_title: str) -> bool:
    """Benennt einen Chat um."""
    db = get_db_connection()
    if db is None:
        return False
    try:
        db.execute("UPDATE chats SET title = ? WHERE id = ?", (new_title, chat_id))
        db.commit()
        return True
    except Exception as e:
        _st_error(f"Fehler beim Umbenennen: {e}")
        return False


# ==============================================================================
# 3. DATEN-ABRUF
# ==============================================================================


def get_chat_list() -> List[Dict]:
    """Lädt alle Chats, sortiert nach letzter Aktivität."""
    db = get_db_connection()
    if db is None:
        return []
    try:
        rows = db.execute(
            """SELECT id, title, last_updated, created_at, chunk_count
               FROM chats
               ORDER BY last_updated DESC"""
        ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"] or "Ohne Titel",
                "lastUpdated": r["last_updated"],
                "chunk_count": r["chunk_count"] or 0,
            }
            for r in rows
        ]
    except Exception as e:
        _st_error(f"❌ Fehler beim Laden der Chat-Liste: {e}")
        return []


def load_chat_history(chat_id: str) -> List[Dict]:
    """
    Lädt Chat-Historie:
    [{'role': ..., 'parts': [{'text': ...}]}]
    """
    db = get_db_connection()
    if db is None:
        return []
    try:
        rows = db.execute(
            """SELECT id, role, content, timestamp FROM messages
               WHERE chat_id = ?
               ORDER BY timestamp ASC""",
            (chat_id,),
        ).fetchall()
        # Phase 6.5: ID und Timestamp für Editor-Funktionen laden
        return [
            {
                "role": r["role"], 
                "parts": [{"text": r["content"]}],
                "id": r["id"],
                "timestamp": r["timestamp"]
            } 
            for r in rows
        ]
    except Exception as e:
        _st_error(f"Fehler beim Laden der Chat-Historie: {e}")
        return []


# ==============================================================================
# 4. SETTINGS
# ==============================================================================


def load_global_settings(default_settings: Dict) -> Dict:
    """Lädt globale Settings aus SQLite. Fällt auf defaults zurück."""
    db = get_db_connection()
    if db is None:
        return default_settings
    try:
        rows = db.execute("SELECT key, value FROM settings").fetchall()
        if not rows:
            return default_settings

        stored = {}
        for r in rows:
            try:
                stored[r["key"]] = json.loads(r["value"])
            except (json.JSONDecodeError, TypeError):
                stored[r["key"]] = r["value"]

        # Merge: defaults als Fallback für fehlende Keys
        return {
            "model_name": stored.get("model_name", default_settings.get("model_name")),
            "temperature": stored.get(
                "temperature", default_settings.get("temperature")
            ),
            "top_p": stored.get("top_p", default_settings.get("top_p")),
            "system_instruction": stored.get(
                "system_instruction", default_settings.get("system_instruction")
            ),
            "use_search": stored.get("use_search", default_settings.get("use_search")),
            "debug_mode": stored.get("debug_mode", default_settings.get("debug_mode")),
        }
    except Exception as e:
        logger.warning(f"Settings-Ladefehler, nutze Defaults: {e}")
        return default_settings


@_db_write
def save_global_settings(
    model_name: str,
    temperature: float,
    top_p: float,
    system_instruction: str,
    use_search: bool,
    debug_mode: bool,
) -> bool:
    """Speichert globale Settings in SQLite."""
    db = get_db_connection()
    if db is None:
        return False
    try:
        settings = {
            "model_name": model_name,
            "temperature": temperature,
            "top_p": top_p,
            "system_instruction": system_instruction,
            "use_search": use_search,
            "debug_mode": debug_mode,
        }
        now = datetime.utcnow().isoformat()
        for key, value in settings.items():
            db.execute(
                """INSERT INTO settings (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = excluded.updated_at""",
                (key, json.dumps(value), now),
            )
        db.commit()
        return True
    except Exception as e:
        _st_error(f"❌ Fehler beim Speichern: {e}")
        return False


# ==============================================================================
# 5. KI-HELFER
# ==============================================================================


def generate_and_update_title(chat_id: str, history: List[Dict]) -> Optional[str]:
    """
    Generiert einen Chat-Titel via LLM.
    v52.2: @_db_write DEKORATOR ENTFERNT, um Deadlock bei LLM-Calls zu verhindern.
    Der DB-Schreibzugriff wird intern durch 'with _db_lock:' abgesichert.
    """
    if not history:
        return None
    try:
        conversation_text = ""
        for msg in history[:4]:
            role = msg.get("role", "")
            text = ""
            if "parts" in msg and msg["parts"]:
                text = msg["parts"][0].get("text", "")
            elif "content" in msg:
                text = msg["content"]
            conversation_text += f"{role}: {text[:300]}\n"

        prompt = (
            "Fasse den folgenden Gesprächsanfang in einem prägnanten Titel "
            "mit maximal 5 Wörtern zusammen. "
            "Antworte NUR mit dem Titel, ohne Anführungszeichen.\n\n"
            f"Gespräch:\n---\n{conversation_text}\n---\nTitel:"
        )

        # --- SCHRITT 1: LLM Call (AUSSERHALB des Locks!) ---
        # Phase 6.5 Fix: Nutze llm_wrapper statt rohem API Call (Vertex-Kompatibilität)
        try:
            from modules.llm_wrapper import llm_call
            new_title = llm_call(
                prompt, 
                task="title_generation", 
                system_instruction="Antworte NUR mit dem Titel, ohne Anführungszeichen.",
                temperature=0.3
            )
            if new_title:
                new_title = new_title.strip().strip("\"'")
        except Exception as e:
            logger.warning(f"⚠️ Titelgenerierung LLM-Call fehlgeschlagen: {e}")
            new_title = None

        # --- SCHRITT 2: DB Update (INNERHALB des Locks) ---
        with _db_lock:
            db = get_db_connection()
            if db:
                db.execute(
                    "UPDATE chats SET title = ? WHERE id = ?", (new_title, chat_id)
                )
                db.commit()

        # Streamlit Session State (optional)
        # WICHTIG: Muss auch bei Fehlern auf True gesetzt werden, 
        # damit Streamlit nicht in einer Endlos-Rerun-Schleife festsitzt!
        if _STREAMLIT_AVAILABLE:
            try:
                st.session_state.title_generated = True
            except Exception:
                pass

        logger.info(f"✅ Titel generiert: '{new_title}'")
        return new_title

    except Exception as e:
        logger.warning(f"Titelgenerierung fehlgeschlagen: {e}")
        return None


# ==============================================================================
# 6. ADMIN-TOOLS (Vector Admin, Re-Indizierung)
# ==============================================================================


def get_all_chats_metadata() -> List[Dict]:
    """Admin: Alle Chats mit Metadaten für das Admin-Dashboard."""
    db = get_db_connection()
    if db is None:
        return []
    try:
        rows = db.execute(
            """SELECT id, title, model_name, created_at
               FROM chats
               ORDER BY last_updated DESC"""
        ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"] or "Ohne Titel",
                "model_name": r["model_name"] or "Unbekannt",
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Fehler beim Laden der Chat-Metadaten: {e}")
        return []


@_db_write
def update_chat_metadata(chat_id: str, **kwargs) -> bool:
    """
    Admin: Aktualisiert Metadaten eines Chats.
    Identische Signatur: update_chat_metadata(chat_id, model_name="Gemma")
    """
    db = get_db_connection()
    if db is None:
        return False
    try:
        # Bekannte Spalten direkt updaten, Rest in metadata-JSON
        known_columns = {"title", "model_name"}
        direct = {k: v for k, v in kwargs.items() if k in known_columns}

        if direct:
            set_clause = ", ".join(f"{k} = ?" for k in direct)
            values = list(direct.values()) + [chat_id]
            db.execute(f"UPDATE chats SET {set_clause} WHERE id = ?", values)
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Fehler beim Update der Metadaten: {e}")
        return False


def get_raw_chat_messages(chat_id: str) -> List[Dict]:
    """Admin: Rohe Nachrichten für Re-Indizierung."""
    db = get_db_connection()
    if db is None:
        return []
    try:
        rows = db.execute(
            """SELECT id, chat_id, role, content, timestamp, metadata
               FROM messages
               WHERE chat_id = ?
               ORDER BY timestamp ASC""",
            (chat_id,),
        ).fetchall()
        messages = []
        for r in rows:
            msg = dict(r)
            if msg.get("metadata"):
                try:
                    msg["metadata"] = json.loads(msg["metadata"])
                except (json.JSONDecodeError, TypeError):
                    pass
            messages.append(msg)
        return messages
    except Exception as e:
        logger.error(f"Fehler beim Laden der Raw-Messages: {e}")
        return []


# ==============================================================================
# A.3: ANALYSIS PERSISTENZ
# ==============================================================================

@_db_write
def save_analysis(
    analysis_id: str,
    query: str,
    answer_text: str,
    intent: Optional[str] = None,
    semantic_intent: Optional[str] = None,
    analysis_domain: str = "analysis_pipeline",
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    seed: Optional[int] = None,
    top_p: Optional[float] = None,
    cited_document_ids: Optional[List[str]] = None,
) -> bool:
    """Persistiert eine Analyse in der Datenbank."""
    db = get_db_connection()
    if db is None:
        return False
    try:
        cited_json = json.dumps(cited_document_ids) if cited_document_ids else None
        db.execute(
            """INSERT INTO analyses
               (analysis_id, query, answer_text, intent, semantic_intent,
                analysis_domain, model, temperature, seed, top_p, cited_document_ids)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (analysis_id, query, answer_text, intent, semantic_intent,
             analysis_domain, model, temperature, seed, top_p, cited_json),
        )
        db.commit()
        logger.info(f"💾 Analyse {analysis_id} persistiert (A.3).")
        return True
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern der Analyse: {e}")
        return False


def get_analysis_list(limit: int = 50) -> List[Dict]:
    """Lazy-Loading: Liste der gespeicherten Analysen (schlank, ohne answer_text)."""
    db = get_db_connection()
    if db is None:
        return []
    try:
        rows = db.execute(
            """SELECT analysis_id, timestamp, query, intent, semantic_intent,
                      analysis_domain, model, temperature, seed, top_p,
                      substr(answer_text, 1, 200) AS preview
               FROM analyses
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Analyse-Liste: {e}")
        return []


def get_analysis_by_id(analysis_id: str) -> Optional[Dict]:
    """Lädt eine einzelne Analyse vollständig (für Detail-Ansicht/Download)."""
    db = get_db_connection()
    if db is None:
        return None
    try:
        row = db.execute(
            """SELECT * FROM analyses WHERE analysis_id = ?""",
            (analysis_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        if result.get("cited_document_ids"):
            try:
                result["cited_document_ids"] = json.loads(result["cited_document_ids"])
            except (json.JSONDecodeError, TypeError):
                result["cited_document_ids"] = []
        else:
            result["cited_document_ids"] = []
        return result
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Analyse {analysis_id}: {e}")
        return None


# ==============================================================================
# A.7: ENFORCER REVIEWS (Human-in-the-Loop)
# ==============================================================================

@_db_write
def insert_enforcer_review(
    id: str,
    claim_hash: str,
    claim_text: str,
    source_id: str,
    source_content: str,
    source_content_hash: str,
    enforcer_version: str,
    enforcer_valid: bool,
    enforcer_reason: Optional[str] = None,
    enforcer_confidence: Optional[float] = None,
) -> bool:
    """Speichert einen Enforcer-Claim für Human-in-the-Loop Review."""
    db = get_db_connection()
    if db is None:
        return False
    try:
        before = db.total_changes
        db.execute(
            """INSERT OR IGNORE INTO enforcer_reviews
               (id, claim_hash, claim_text, source_id, source_content,
                source_content_hash, enforcer_version, enforcer_valid, enforcer_reason,
                enforcer_confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (id, claim_hash, claim_text, source_id, source_content,
             source_content_hash, enforcer_version, 1 if enforcer_valid else 0, enforcer_reason,
             enforcer_confidence),
        )
        db.commit()
        return (db.total_changes - before) > 0
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern des Enforcer-Reviews: {e}")
        return False


def get_unreviewed_reviews(limit: int = 8, offset: int = 0) -> List[Dict]:
    """Lädt unreviewed Enforcer-Reviews (Pagination für UI)."""
    db = get_db_connection()
    if db is None:
        return []
    try:
        rows = db.execute(
            """SELECT * FROM enforcer_reviews
               WHERE human_valid IS NULL
               ORDER BY created_at ASC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der unreviewed Reviews: {e}")
        return []


def get_unreviewed_count() -> int:
    """Anzahl der offenen Reviews (für Badge in Sidebar)."""
    db = get_db_connection()
    if db is None:
        return 0
    try:
        row = db.execute(
            "SELECT COUNT(*) FROM enforcer_reviews WHERE human_valid IS NULL"
        ).fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"❌ Fehler beim Zählen der offenen Reviews: {e}")
        return 0


@_db_write
def mark_reviewed(
    review_id: str, valid: bool, comment: Optional[str] = None, reviewer: Optional[str] = None
) -> bool:
    """Markiert einen Review als human-reviewed."""
    db = get_db_connection()
    if db is None:
        return False
    try:
        from datetime import datetime
        before = db.total_changes
        db.execute(
            """UPDATE enforcer_reviews
               SET human_valid = ?, human_comment = ?, reviewed_at = ?, reviewer = ?
               WHERE id = ?""",
            (1 if valid else 0, comment, datetime.now().isoformat(), reviewer, review_id),
        )
        db.commit()
        return (db.total_changes - before) > 0
    except Exception as e:
        logger.error(f"❌ Fehler beim Markieren des Reviews {review_id}: {e}")
        return False


def get_human_review_count() -> int:
    """Gibt die Anzahl bereits human-reviewed Claims zurück."""
    db = get_db_connection()
    if db is None:
        return 0
    try:
        row = db.execute(
            "SELECT COUNT(*) FROM enforcer_reviews WHERE human_valid IS NOT NULL"
        ).fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"❌ Fehler beim Zählen der human reviews: {e}")
        return 0


# ==============================================================================
# A.16: CORPUS STATISTICS (Dashboard-Daten)
# ==============================================================================

def get_chat_count() -> int:
    """Gesamtanzahl Chats in der Datenbank."""
    db = get_db_connection()
    if db is None:
        return 0
    try:
        row = db.execute("SELECT COUNT(*) FROM chats").fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"❌ Fehler beim Zählen der Chats: {e}")
        return 0


def get_message_count() -> int:
    """Gesamtanzahl Nachrichten in der Datenbank."""
    db = get_db_connection()
    if db is None:
        return 0
    try:
        row = db.execute("SELECT COUNT(*) FROM messages").fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"❌ Fehler beim Zählen der Nachrichten: {e}")
        return 0


def get_orphan_chat_count() -> int:
    """Chats ohne Chunk-Registry-Einträge (chunk_count = 0)."""
    db = get_db_connection()
    if db is None:
        return 0
    try:
        row = db.execute(
            "SELECT COUNT(*) FROM chats WHERE chunk_count = 0 OR chunk_count IS NULL"
        ).fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"❌ Fehler beim Zählen der Orphan-Chats: {e}")
        return 0


def get_hashed_chunk_count() -> int:
    """Chunks mit gesetztem content_hash (A.13 Deduplizierung)."""
    db = get_db_connection()
    if db is None:
        return 0
    try:
        row = db.execute(
            "SELECT COUNT(*) FROM chunk_registry WHERE content_hash IS NOT NULL"
        ).fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"❌ Fehler beim Zählen der gehashten Chunks: {e}")
        return 0


def get_unique_hash_count() -> int:
    """Anzahl eindeutiger content_hash-Werte in der Registry."""
    db = get_db_connection()
    if db is None:
        return 0
    try:
        row = db.execute(
            "SELECT COUNT(DISTINCT content_hash) FROM chunk_registry WHERE content_hash IS NOT NULL"
        ).fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"❌ Fehler beim Zählen der eindeutigen Hashes: {e}")
        return 0


def get_chunk_timeline() -> List[Dict]:
    """
    Wöchentliche Chunk-Erstellung über Zeit.
    Returns: Liste von Dicts mit 'week' und 'count'.
    """
    db = get_db_connection()
    if db is None:
        return []
    try:
        rows = db.execute(
            """
            SELECT
                strftime('%Y-W%W', created_at) as week,
                COUNT(*) as count
            FROM chunk_registry
            WHERE created_at IS NOT NULL
            GROUP BY week
            ORDER BY week
            """
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Chunk-Timeline: {e}")
        return []


# ==============================================================================
# A.8: CONFIDENCE CALIBRATION (Reliability Diagram + ECE)
# ==============================================================================

def get_calibration_data(enforcer_version: Optional[str] = None) -> List[Dict]:
    """
    Lädt human-reviewed Claims mit Confidence für Kalibrierungsanalyse.

    Returns:
        Liste von Dicts mit keys: enforcer_confidence, human_valid
    """
    db = get_db_connection()
    if db is None:
        return []
    try:
        sql = """
            SELECT enforcer_confidence, human_valid
            FROM enforcer_reviews
            WHERE human_valid IS NOT NULL
              AND enforcer_confidence IS NOT NULL
        """
        params = ()
        if enforcer_version:
            sql += " AND enforcer_version = ?"
            params = (enforcer_version,)
        rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Kalibrierungsdaten: {e}")
        return []


def calculate_ece(calibration_data: List[Dict], n_bins: int = 5) -> Tuple[float, List[Dict]]:
    """
    Berechnet Expected Calibration Error (ECE) über gefüllte Bins.

    Args:
        calibration_data: Liste von {"enforcer_confidence": float, "human_valid": 0/1}
        n_bins: Anzahl Bins (default 5 für 0.0-0.2, 0.2-0.4, ...)

    Returns:
        Tuple: (ece_score, bins_info)
        bins_info: Liste mit {"bin_idx", "bin_center", "count", "accuracy", "avg_confidence"}
    """
    import statistics
    import math

    # Bins initialisieren (immer zurückgeben, auch bei leeren Daten)
    bin_width = 1.0 / n_bins
    bins = [
        {
            "bin_idx": i,
            "bin_center": round((i + 0.5) * bin_width, 2),
            "items": [],
            "confidences": [],
        }
        for i in range(n_bins)
    ]

    if not calibration_data:
        bins_info = [
            {
                "bin_idx": b["bin_idx"],
                "bin_center": b["bin_center"],
                "count": 0,
                "accuracy": None,
                "avg_confidence": None,
            }
            for b in bins
        ]
        return 0.0, bins_info

    # Daten in Bins einteilen
    for item in calibration_data:
        conf = item.get("enforcer_confidence")
        if conf is None or math.isnan(conf):
            continue
        # Letzter Bin für confidence=1.0
        if conf >= 1.0:
            idx = n_bins - 1
        else:
            idx = int(conf / bin_width)
            idx = min(idx, n_bins - 1)
        bins[idx]["items"].append(1 if item.get("human_valid") else 0)
        bins[idx]["confidences"].append(conf)

    bins_info = []
    filled_bins = 0
    for b in bins:
        count = len(b["items"])
        if count > 0:
            filled_bins += 1
            accuracy = sum(b["items"]) / count
            avg_conf = statistics.mean(b["confidences"])
            bins_info.append({
                "bin_idx": b["bin_idx"],
                "bin_center": b["bin_center"],
                "count": count,
                "accuracy": round(accuracy, 4),
                "avg_confidence": round(avg_conf, 4),
            })
        else:
            bins_info.append({
                "bin_idx": b["bin_idx"],
                "bin_center": b["bin_center"],
                "count": 0,
                "accuracy": None,
                "avg_confidence": None,
            })

    total_samples = sum(b["count"] for b in bins_info if b["count"] > 0)
    if total_samples == 0:
        return 0.0, bins_info

    ece = sum(
        b["count"] / total_samples * abs(b["accuracy"] - b["avg_confidence"])
        for b in bins_info
        if b["count"] > 0
    )

    return round(ece, 4), bins_info


# ==============================================================================
# A.8 Ende
# ==============================================================================

# ==============================================================================
# Phase 4.3: CHUNK REGISTRY (SQLite treibt, ChromaDB folgt)
# ==============================================================================

@_db_write
def register_chunks(chat_id: str, chunk_ids: List[str], content_hashes: List[str] = None) -> int:
    """
    Registriert Chunk-IDs in der SQLite-Registry nach ChromaDB-Import.
    Bulk-Insert mit INSERT OR IGNORE (idempotent).
    A.13: Optional content_hashes für Deduplizierung.

    Returns:
        Anzahl tatsächlich eingefügter Einträge.
    """
    if not chunk_ids:
        return 0
    db = get_db_connection()
    if db is None:
        return 0
    try:
        before = db.total_changes
        now = datetime.utcnow().isoformat()
        if content_hashes and len(content_hashes) == len(chunk_ids):
            db.executemany(
                """INSERT OR IGNORE INTO chunk_registry (chunk_id, chat_id, created_at, content_hash)
                   VALUES (?, ?, ?, ?)""",
                list(zip(chunk_ids, [chat_id] * len(chunk_ids), [now] * len(chunk_ids), content_hashes)),
            )
        else:
            db.executemany(
                """INSERT OR IGNORE INTO chunk_registry (chunk_id, chat_id, created_at)
                   VALUES (?, ?, ?)""",
                [(cid, chat_id, now) for cid in chunk_ids],
            )
        db.commit()
        inserted = db.total_changes - before
        logger.info(f"✅ Chunk Registry: {inserted}/{len(chunk_ids)} IDs für {chat_id[-8:]} registriert.")
        return inserted
    except Exception as e:
        logger.error(f"❌ Chunk Registry Insert fehlgeschlagen: {e}")
        return 0


def is_duplicate_chunk(content_hash: str) -> bool:
    """
    A.13: Prüft ob ein Chunk mit diesem content_hash bereits existiert.
    Schnell dank idx_chunk_registry_hash.
    """
    if not content_hash:
        return False
    db = get_db_connection()
    if db is None:
        return False
    try:
        row = db.execute(
            "SELECT 1 FROM chunk_registry WHERE content_hash = ? LIMIT 1",
            (content_hash,),
        ).fetchone()
        return row is not None
    except Exception as e:
        logger.warning(f"⚠️ Deduplizierungs-Check fehlgeschlagen: {e}")
        return False


@_db_write
def unregister_chat_chunks(chat_id: str) -> int:
    """
    Entfernt alle Registry-Einträge eines Chats (nach Delete).

    Returns:
        Anzahl gelöschter Einträge.
    """
    db = get_db_connection()
    if db is None:
        return 0
    try:
        before = db.total_changes
        db.execute("DELETE FROM chunk_registry WHERE chat_id = ?", (chat_id,))
        db.commit()
        deleted = db.total_changes - before
        logger.info(f"🗑️ Chunk Registry: {deleted} Einträge für {chat_id[-8:]} entfernt.")
        return deleted
    except Exception as e:
        logger.error(f"❌ Chunk Registry Delete fehlgeschlagen: {e}")
        return 0


def get_chunk_ids_page(
    chat_id: Optional[str] = None,
    last_seq: int = 0,
    limit: int = 50,
) -> Tuple[List[str], int]:
    """
    Keyset-Pagination über chunk_registry.

    Args:
        chat_id: Optional — wenn None, alle Chunks paginieren.
        last_seq: seq-Cursor der letzten Seite (0 für erste Seite).
        limit: Seitengröße.

    Returns:
        (chunk_ids, next_last_seq) — next_last_seq für nächste Seite,
        oder 0 wenn keine weiteren Einträge.
    """
    db = get_db_connection()
    if db is None:
        return [], 0
    try:
        if chat_id:
            rows = db.execute(
                """SELECT chunk_id, seq FROM chunk_registry
                   WHERE chat_id = ? AND seq > ?
                   ORDER BY seq LIMIT ?""",
                (chat_id, last_seq, limit),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT chunk_id, seq FROM chunk_registry
                   WHERE seq > ?
                   ORDER BY seq LIMIT ?""",
                (last_seq, limit),
            ).fetchall()

        if not rows:
            return [], 0

        chunk_ids = [r["chunk_id"] for r in rows]
        next_seq = rows[-1]["seq"]
        return chunk_ids, next_seq
    except Exception as e:
        logger.error(f"❌ Chunk Registry Pagination fehlgeschlagen: {e}")
        return [], 0


def get_chunk_registry_count(chat_id: Optional[str] = None) -> int:
    """Gibt die Anzahl der Registry-Einträge zurück (0 = Backfill nötig)."""
    db = get_db_connection()
    if db is None:
        return 0
    try:
        if chat_id:
            row = db.execute(
                "SELECT COUNT(*) FROM chunk_registry WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        else:
            row = db.execute("SELECT COUNT(*) FROM chunk_registry").fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"❌ Chunk Registry Count fehlgeschlagen: {e}")
        return 0


@_db_write
def update_chunk_count(chat_id: str) -> int:
    """
    Aktualisiert chunk_count in chats aus der Registry (Batch-Update).
    Wird exakt einmal nach Import oder Delete aufgerufen.

    Returns:
        Neue chunk_count.
    """
    db = get_db_connection()
    if db is None:
        return 0
    try:
        db.execute(
            """UPDATE chats
               SET chunk_count = (
                   SELECT COUNT(*) FROM chunk_registry WHERE chat_id = ?
               )
               WHERE id = ?""",
            (chat_id, chat_id),
        )
        db.commit()
        row = db.execute(
            "SELECT chunk_count FROM chats WHERE id = ?", (chat_id,)
        ).fetchone()
        count = row["chunk_count"] if row else 0
        logger.info(f"📊 chunk_count für {chat_id[-8:]} aktualisiert: {count}")
        return count
    except Exception as e:
        logger.error(f"❌ chunk_count Update fehlgeschlagen: {e}")
        return 0


def backfill_chunk_registry(collection) -> int:
    """
    Einmaliger Backfill: ChromaDB → SQLite Registry.
    Prüft zuerst, ob Registry bereits gefüllt ist.

    Args:
        collection: ChromaDB Collection (hat .get() Methode).

    Returns:
        Anzahl eingefügter Einträge.
    """
    existing = get_chunk_registry_count()
    if existing > 0:
        logger.info(f"ℹ️ Chunk Registry bereits gefüllt ({existing} Einträge). Kein Backfill.")
        return 0

    logger.info("🔄 Starte Chunk Registry Backfill aus ChromaDB...")
    try:
        all_ids = collection.get(include=[])["ids"]
        if not all_ids:
            logger.info("ℹ️ ChromaDB leer — Registry bleibt leer.")
            return 0

        total_inserted = 0
        BATCH = 500
        db = get_db_connection()
        if db is None:
            return 0

        for i in range(0, len(all_ids), BATCH):
            batch_ids = all_ids[i : i + BATCH]
            result = collection.get(ids=batch_ids, include=["metadatas"])
            entries = []
            now = datetime.utcnow().isoformat()
            for chunk_id, meta in zip(result["ids"], result["metadatas"]):
                cid = meta.get("chat_id", "unknown") if meta else "unknown"
                entries.append((chunk_id, cid, now))

            if entries:
                with _db_lock:
                    db.executemany(
                        """INSERT OR IGNORE INTO chunk_registry (chunk_id, chat_id, created_at)
                           VALUES (?, ?, ?)""",
                        entries,
                    )
                    db.commit()
                total_inserted += len(entries)
                logger.info(f"  🔄 Backfill: {total_inserted}/{len(all_ids)} Chunks...")

        logger.info(f"✅ Chunk Registry Backfill abgeschlossen: {total_inserted} Einträge.")
        return total_inserted
    except Exception as e:
        logger.error(f"❌ Chunk Registry Backfill fehlgeschlagen: {e}")
        return 0


# ==============================================================================
# Phase 4.3 Ende
# ==============================================================================

def rebuild_fts_index() -> Tuple[int, int]:
    """
    Befüllt den FTS5-Index einmalig aus dem bestehenden messages-Bestand.
    Nötig für: Erstmigration + manuelle Reparatur.
    Danach übernehmen die Trigger die Synchronisierung automatisch.
    """
    db = get_db_connection()
    if db is None:
        return 0, 0
    try:
        # messages_fts zurücksetzen
        db.execute("DELETE FROM messages_fts")
        db.execute("""
            INSERT INTO messages_fts(rowid, content, chat_id)
            SELECT rowid, content, chat_id FROM messages
        """)
        msg_count = db.execute("SELECT COUNT(*) as n FROM messages_fts").fetchone()["n"]

        # chats_fts zurücksetzen (A.16)
        db.execute("DELETE FROM chats_fts")
        db.execute("""
            INSERT INTO chats_fts(rowid, title)
            SELECT rowid, title FROM chats
        """)
        chat_count = db.execute("SELECT COUNT(*) as n FROM chats_fts").fetchone()["n"]

        db.commit()
        logger.info(f"✅ FTS5-Index rebuilt: {msg_count} Messages, {chat_count} Chats")
        return msg_count, chat_count
    except Exception as e:
        logger.error(f"❌ FTS5 rebuild fehlgeschlagen: {e}")
        return 0, 0


def _sanitize_fts5_term(word: str) -> str:
    """Entfernt alle Zeichen, die FTS5 als Operatoren oder Sonderzeichen
    interpretieren könnte.

    Erlaubt: Unicode-Buchstaben, Zahlen, Underscore (alles, was FTS5
    tokenize='unicode61' als 'eligible characters' betrachtet).

    Entfernt: Anführungszeichen, *, -, ^, (, ), <, >, =, ', ;,
    sowie implizite Operatoren (OR, AND, NOT, NEAR) als Literale.
    """
    return re.sub(r'[^\w]', '', word, flags=re.UNICODE)


def search_chats_by_content(term: str, limit: int = 50) -> List[Dict]:
    """
    Volltext-Suche über alle Nachrichten via FTS5.
    Gibt deduplizierte Chat-Liste zurück —
    gleiche Struktur wie get_chat_list(), direkt kompatibel.

    Query-Strategie: Prefix-Suche pro Wort ("adorno"* matcht "Adorno", "Adornos").
    Mehrere Wörter: AND-verknüpft.
    Sonderzeichen werden entfernt (nicht nur escaped), um FTS5-Query-Injection
    und Syntax-Fehler zu verhindern.
    """
    db = get_db_connection()
    if db is None:
        return []

    # SEC-6: Sichere FTS5-Query — strikte Sanitisierung auf alphanumerische Zeichen
    words = term.strip().split()
    safe_words = [_sanitize_fts5_term(w) for w in words]
    safe_words = [w for w in safe_words if w]
    if not safe_words:
        return []
    fts_query = " ".join(f'"{w}"*' for w in safe_words)

    try:
        rows = db.execute(
            """
            SELECT DISTINCT c.id, c.title, c.last_updated, c.chunk_count
            FROM messages_fts f
            JOIN chats c ON c.id = f.chat_id
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """,
            (fts_query, limit),
        ).fetchall()

        return [
            {
                "id": r["id"],
                "title": r["title"] or "Ohne Titel",
                "lastUpdated": r["last_updated"],
                "chunk_count": r["chunk_count"] or 0,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"❌ FTS5-Suche fehlgeschlagen (Query: '{fts_query}'): {e}")
        # Fallback auf Titel-Suche, damit die UI nicht einfriert
        return []


def search_chats_by_title(term: str, limit: int = 50) -> List[Dict]:
    """
    A.16: FTS5-Suche über Chat-Titel via chats_fts.
    Gibt deduplizierte Chat-Liste zurück —
    gleiche Struktur wie get_chat_list(), direkt kompatibel.
    """
    db = get_db_connection()
    if db is None:
        return []

    words = term.strip().split()
    safe_words = [_sanitize_fts5_term(w) for w in words]
    safe_words = [w for w in safe_words if w]
    if not safe_words:
        return []
    fts_query = " ".join(f'"{w}"*' for w in safe_words)

    try:
        rows = db.execute(
            """
            SELECT c.id, c.title, c.last_updated, c.chunk_count
            FROM chats_fts f
            JOIN chats c ON c.rowid = f.rowid
            WHERE chats_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()

        return [
            {
                "id": r["id"],
                "title": r["title"] or "Ohne Titel",
                "lastUpdated": r["last_updated"],
                "chunk_count": r["chunk_count"] or 0,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"❌ FTS5-Titel-Suche fehlgeschlagen (Query: '{fts_query}'): {e}")
        return []
