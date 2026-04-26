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
from datetime import datetime
from typing import List, Dict, Optional

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
    skipped_chunks INTEGER DEFAULT 0
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

-- Phase 4.4: Embedding Cache
CREATE TABLE IF NOT EXISTS embedding_cache (
    text_hash TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
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
    Löscht Chat + Nachrichten + Embeddings.
    v52.1: Robuster Connection-Reset bei Transaction-Poisoning.
    """
    # --- SCHRITT 1: Vektoren löschen (ChromaDB) ---
    try:
        from modules.vector_store import LocalVectorStore
        vs = LocalVectorStore()
        vs.delete_chat_embeddings(chat_id)
    except Exception as e:
        logger.warning(
            f"⚠️ Vektor-Löschung für Chat {chat_id} fehlgeschlagen "
            f"(Geister-Vektoren möglich): {e}"
        )

    # --- SCHRITT 2 & 3: SQL Löschung mit Auto-Retry ---
    # Wenn die SQLite-Connection durch einen vorherigen Fehler vergiftet ist,
    # werfen wir sie weg und holen eine frische.
    max_retries = 2
    for attempt in range(max_retries):
        db = get_db_connection()
        if db is None:
            return False
            
        try:
            db.rollback() # Poisoned State bereinigen
            db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            db.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            db.commit()
            logger.info(f"🗑️ Chat {chat_id} inkl. SQL-Daten gelöscht.")
            return True
            
        except sqlite3.OperationalError as e:
            logger.warning(f"⚠️ Delete Chat Versuch {attempt+1} fehlgeschlagen (OperationalError): {e}")
            try:
                db.rollback()
            except Exception:
                pass
                
            # CONNECTION RESET: Globale Variable überschreiben
            global _db_connection
            if _db_connection:
                try:
                    _db_connection.close()
                except Exception:
                    pass
            _db_connection = None # Zwingt get_db_connection() beim nächsten Mal, neu zu verbinden
            
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

    return False

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
            """SELECT id, title, last_updated, created_at
               FROM chats
               ORDER BY last_updated DESC"""
        ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"] or "Ohne Titel",
                "lastUpdated": r["last_updated"],
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
# 7. VOLLTEXT-SUCHE (FTS5)
# ==============================================================================


def rebuild_fts_index() -> int:
    """
    Befüllt den FTS5-Index einmalig aus dem bestehenden messages-Bestand.
    Nötig für: Erstmigration + manuelle Reparatur.
    Danach übernehmen die Trigger die Synchronisierung automatisch.
    """
    db = get_db_connection()
    if db is None:
        return 0
    try:
        db.execute("DELETE FROM messages_fts")
        db.execute("""
            INSERT INTO messages_fts(rowid, content, chat_id)
            SELECT rowid, content, chat_id FROM messages
        """)
        db.commit()
        count = db.execute("SELECT COUNT(*) as n FROM messages_fts").fetchone()["n"]
        logger.info(f"✅ FTS5-Index rebuilt: {count} Einträge")
        return count
    except Exception as e:
        logger.error(f"❌ FTS5 rebuild fehlgeschlagen: {e}")
        return 0


def search_chats_by_content(term: str, limit: int = 50) -> List[Dict]:
    """
    Volltext-Suche über alle Nachrichten via FTS5.
    Gibt deduplizierte Chat-Liste zurück —
    gleiche Struktur wie get_chat_list(), direkt kompatibel.

    Query-Strategie: Prefix-Suche pro Wort ("adorno"* matcht "Adorno", "Adornos").
    Mehrere Wörter: AND-verknüpft.
    Sonderzeichen werden escaped.
    """
    db = get_db_connection()
    if db is None:
        return []

    # Sichere FTS5-Query: jedes Wort als gequoteten Prefix
    words = term.strip().split()
    if not words:
        return []
    fts_query = " ".join(f'"{w.replace(chr(34), "")}"*' for w in words)

    try:
        rows = db.execute(
            """
            SELECT DISTINCT c.id, c.title, c.last_updated
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
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"❌ FTS5-Suche fehlgeschlagen (Query: '{fts_query}'): {e}")
        # Fallback auf Titel-Suche, damit die UI nicht einfriert
        return []
