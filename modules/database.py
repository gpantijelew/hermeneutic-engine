# modules/database.py — v50.9: SQLite + LM Studio (Drop-in für Firestore)
"""
Datenbankschicht der Hermeneutic Reconstruction Engine.

MIGRATION v50.9:
- Firestore → SQLite (hre_data/hre.db)
- Gemini API → LM Studio via OpenAI-kompatibler API
- @st.cache_resource → robuster Python-Singleton
- Identische öffentliche Schnittstelle: kein anderes Modul muss geändert werden

ÖFFENTLICHE API (unverändert gegenüber Firestore-Version):
- create_chat_in_firestore()      Chat anlegen
- save_message()                  Nachricht speichern
- delete_chat()                   Chat + Embeddings löschen
- rename_chat()                   Chat umbenennen
- get_chat_list()                 Chat-Liste laden
- load_chat_history()             Chat-Historie laden
- generate_and_update_title()     KI-Titel generieren
- load_global_settings()          Settings laden
- save_global_settings()          Settings speichern
- get_all_chats_metadata()        Admin: alle Chats
- update_chat_metadata()          Admin: Metadaten ändern
- get_raw_chat_messages()         Admin: Rohdaten für Re-Indizierung
"""

import sqlite3
import json
import uuid
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from modules.config import (
    SQLITE_PATH,
    get_llm_client,
    MODEL_TITLE_GEN
)
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
    metadata    TEXT
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
"""

# ==============================================================================
# SINGLETON-VERBINDUNG (Robust: Streamlit + Skripte + Migrations-Tools)
# ==============================================================================
_db_connection: Optional[sqlite3.Connection] = None

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
                check_same_thread=False  # Für Multi-Thread (Streamlit)
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(_SCHEMA)
            conn.commit()
            _db_connection = conn
            logger.info(f"✅ SQLite verbunden: {SQLITE_PATH}")
        except Exception as e:
            logger.error(f"❌ SQLite-Verbindungsfehler: {e}")
            _st_error(f"🔥 Datenbankfehler: {e}")
            return None
    return _db_connection

# Rückwärtskompatibiler Alias — falls anderer Code get_firestore_client() importiert
def get_firestore_client():
    """
    Alias für get_db_connection().
    Rückwärtskompatibilität: Module die get_firestore_client() importieren
    erhalten weiterhin eine funktionierende Verbindung.
    """
    return get_db_connection()

# ==============================================================================
# 2. CHAT-MANAGEMENT
# ==============================================================================

def create_chat_in_firestore(title: str = "Neuer Chat") -> Optional[str]:
    """Erstellt einen neuen Chat. Gibt chat_id zurück."""
    db = get_db_connection()
    if db is None:
        return None
    try:
        chat_id = str(uuid.uuid4())
        db.execute(
            """INSERT INTO chats (id, title) VALUES (?, ?)""",
            (chat_id, title)
        )
        db.commit()
        logger.info(f"✅ Chat erstellt: ID={chat_id}, Title={title}")
        return chat_id
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen des Chats: {e}")
        _st_error(f"❌ Fehler beim Erstellen des Chats: {e}")
        return None


def save_message(
    chat_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict] = None
) -> bool:
    """
    Speichert eine Nachricht.
    Identische Signatur zur Firestore-Version inkl. metadata-Support.
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
                json.dumps(metadata) if metadata else None
            )
        )
        db.execute(
            """UPDATE chats SET last_updated = ? WHERE id = ?""",
            (now, chat_id)
        )
        db.commit()
        return True
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern der Nachricht: {e}")
        return False


def delete_chat(chat_id: str) -> bool:
    """
    Löscht Chat + Nachrichten + Embeddings.
    Embeddings-Löschung: TODO Phase 4 (ChromaDB)
    """
    db = get_db_connection()
    if db is None:
        return False
    try:
        # --- SCHRITT 1: Vektoren löschen ---
        # TODO Phase 4: ChromaDB-Äquivalent zu delete_chat_embeddings()
        # from modules.vector_store import LocalVectorStore
        # vector_store = LocalVectorStore()
        # vector_store.delete_chat_embeddings(chat_id)
        logger.info(
            f"⏳ Vektor-Löschung für Chat {chat_id}: "
            f"Ausstehend bis Phase 4 (ChromaDB)."
        )

        # --- SCHRITT 2: Nachrichten löschen ---
        db.execute(
            "DELETE FROM messages WHERE chat_id = ?", (chat_id,)
        )

        # --- SCHRITT 3: Chat-Dokument löschen ---
        db.execute(
            "DELETE FROM chats WHERE id = ?", (chat_id,)
        )
        db.commit()
        logger.info(f"🗑️ Chat {chat_id} gelöscht.")
        return True
    except Exception as e:
        _st_error(f"Fehler beim Löschen des Chats: {e}")
        return False


def rename_chat(chat_id: str, new_title: str) -> bool:
    """Benennt einen Chat um."""
    db = get_db_connection()
    if db is None:
        return False
    try:
        db.execute(
            "UPDATE chats SET title = ? WHERE id = ?",
            (new_title, chat_id)
        )
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
                'id': r['id'],
                'title': r['title'] or 'Ohne Titel',
                'lastUpdated': r['last_updated']
            }
            for r in rows
        ]
    except Exception as e:
        _st_error(f"❌ Fehler beim Laden der Chat-Liste: {e}")
        return []


def load_chat_history(chat_id: str) -> List[Dict]:
    """
    Lädt Chat-Historie im Firestore-kompatiblen Format:
    [{'role': ..., 'parts': [{'text': ...}]}]
    """
    db = get_db_connection()
    if db is None:
        return []
    try:
        rows = db.execute(
            """SELECT role, content FROM messages
               WHERE chat_id = ?
               ORDER BY timestamp ASC""",
            (chat_id,)
        ).fetchall()
        return [
            {
                'role': r['role'],
                'parts': [{'text': r['content']}]
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
        rows = db.execute(
            "SELECT key, value FROM settings"
        ).fetchall()
        if not rows:
            return default_settings

        stored = {}
        for r in rows:
            try:
                stored[r['key']] = json.loads(r['value'])
            except (json.JSONDecodeError, TypeError):
                stored[r['key']] = r['value']

        # Merge: defaults als Fallback für fehlende Keys
        return {
            'model_name':         stored.get('model_name',         default_settings.get('model_name')),
            'temperature':        stored.get('temperature',        default_settings.get('temperature')),
            'top_p':              stored.get('top_p',              default_settings.get('top_p')),
            'system_instruction': stored.get('system_instruction', default_settings.get('system_instruction')),
            'use_search':         stored.get('use_search',         default_settings.get('use_search')),
            'debug_mode':         stored.get('debug_mode',         default_settings.get('debug_mode')),
        }
    except Exception as e:
        logger.warning(f"Settings-Ladefehler, nutze Defaults: {e}")
        return default_settings


def save_global_settings(
    model_name: str,
    temperature: float,
    top_p: float,
    system_instruction: str,
    use_search: bool,
    debug_mode: bool
) -> bool:
    """Speichert globale Settings in SQLite."""
    db = get_db_connection()
    if db is None:
        return False
    try:
        settings = {
            'model_name':         model_name,
            'temperature':        temperature,
            'top_p':              top_p,
            'system_instruction': system_instruction,
            'use_search':         use_search,
            'debug_mode':         debug_mode,
        }
        now = datetime.utcnow().isoformat()
        for key, value in settings.items():
            db.execute(
                """INSERT INTO settings (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = excluded.updated_at""",
                (key, json.dumps(value), now)
            )
        db.commit()
        return True
    except Exception as e:
        _st_error(f"❌ Fehler beim Speichern: {e}")
        return False

# ==============================================================================
# 5. KI-HELFER
# ==============================================================================

def generate_and_update_title(
    chat_id: str,
    history: List[Dict]
) -> Optional[str]:
    """
    Generiert einen Chat-Titel via LM Studio (Qwen 3.5 27B).
    Identische Signatur zur Gemini-Version.
    """
    if not history:
        return None
    try:
        # Kontext aus ersten 4 Nachrichten — identisch zur Firestore-Version
        conversation_text = ""
        for msg in history[:4]:
            role = msg.get('role', '')
            text = ""
            if 'parts' in msg and msg['parts']:
                text = msg['parts'][0].get('text', '')
            elif 'content' in msg:
                text = msg['content']
            conversation_text += f"{role}: {text[:300]}\n"

        prompt = (
            "Fasse den folgenden Gesprächsanfang in einem prägnanten Titel "
            "mit maximal 5 Wörtern zusammen. "
            "Antworte NUR mit dem Titel, ohne Anführungszeichen.\n\n"
            f"Gespräch:\n---\n{conversation_text}\n---\nTitel:"
        )

        client, model = get_llm_client()
        response = client.chat.completions.create(
            model=model,
            messages=[
                   {"role": "system", "content": get_system_message()},
                   {"role": "user", "content": prompt}
             ]
            max_tokens=30,
            temperature=0.3
        )
        new_title = response.choices[0].message.content.strip().strip('"\'')

        # In SQLite speichern
        db = get_db_connection()
        if db:
            db.execute(
                "UPDATE chats SET title = ? WHERE id = ?",
                (new_title, chat_id)
            )
            db.commit()

        # Streamlit Session State (optional)
        if _STREAMLIT_AVAILABLE:
            try:
                if 'title_generated' not in st.session_state:
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
                'id':         r['id'],
                'title':      r['title'] or 'Ohne Titel',
                'model_name': r['model_name'] or 'Unbekannt',
                'created_at': r['created_at']
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Fehler beim Laden der Chat-Metadaten: {e}")
        return []


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
        known_columns = {'title', 'model_name'}
        direct = {k: v for k, v in kwargs.items() if k in known_columns}
        
        if direct:
            set_clause = ", ".join(f"{k} = ?" for k in direct)
            values = list(direct.values()) + [chat_id]
            db.execute(
                f"UPDATE chats SET {set_clause} WHERE id = ?",
                values
            )
            db.commit()
        return True
    except Exception as e:
        logger.error(f"Fehler beim Update der Metadaten: {e}")
        raise e


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
            (chat_id,)
        ).fetchall()
        messages = []
        for r in rows:
            msg = dict(r)
            if msg.get('metadata'):
                try:
                    msg['metadata'] = json.loads(msg['metadata'])
                except (json.JSONDecodeError, TypeError):
                    pass
            messages.append(msg)
        return messages
    except Exception as e:
        logger.error(f"Fehler beim Laden der Raw-Messages: {e}")
        return []