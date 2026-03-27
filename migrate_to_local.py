# migrate_to_local.py — einmaliges Migrations-Skript
"""
Phase 5: Firestore-Export → ChromaDB + SQLite
Liest export_chunks.json, export_chats.json, export_settings.json
und befüllt die neue lokale Infrastruktur.
"""

import json
import time
from pathlib import Path
from modules.vector_store import FirestoreVectorStore, _get_chroma_collection
from modules.database import get_db_connection

print("=== HRE Migration: Firestore → Lokal ===\n")

vs = FirestoreVectorStore()
collection = _get_chroma_collection()
db = get_db_connection()

# ─── SCHRITT 1: Chunks re-embedden ────────────────────────────────────────────
print("Schritt 1: Chunks laden und in ChromaDB indizieren...")
print("(Das dauert ~10-15 Minuten — RTX 3090 ist am Werk)\n")

with open("export_chunks.json", encoding="utf-8") as f:
    chunks = json.load(f)

total = len(chunks)
stored = 0
skipped = 0
start_time = time.time()

BATCH_SIZE = 100
batch_ids, batch_embeddings = [], []
batch_documents, batch_metadatas = [], []

for idx, chunk in enumerate(chunks):
    text = chunk.get("text", "").strip()
    if not text or len(text) < 50:
        skipped += 1
        continue

    # Embedding erzeugen
    vec = vs._get_embedding(text)
    if not vec:
        skipped += 1
        continue

    # Metadaten bereinigen (ChromaDB: nur str/int/float/bool)
    raw_meta = chunk.get("metadata", {}) or {}
    clean_meta = {
        k: (v if isinstance(v, (str, int, float, bool)) else str(v))
        for k, v in raw_meta.items()
        if v is not None
    }
    # chat_id sicherstellen (wichtig für Filter)
    if "chat_id" not in clean_meta:
        clean_meta["chat_id"] = chunk.get("id", "").split("_")[0]

    batch_ids.append(chunk["id"])
    batch_embeddings.append(vec)
    batch_documents.append(text)
    batch_metadatas.append(clean_meta)
    stored += 1

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

        elapsed = time.time() - start_time
        rate = stored / elapsed
        eta = (total - idx) / rate if rate > 0 else 0
        print(
            f"  💾 {stored}/{total} Chunks "
            f"({rate:.1f}/s — ETA: {eta/60:.1f} min)"
        )

# Finaler Batch
if batch_ids:
    collection.upsert(
        ids=batch_ids,
        embeddings=batch_embeddings,
        documents=batch_documents,
        metadatas=batch_metadatas
    )

elapsed_total = time.time() - start_time
print(f"\n✅ Chunks: {stored} indiziert, {skipped} übersprungen")
print(f"⏱️  Gesamtzeit: {elapsed_total/60:.1f} Minuten\n")

# ─── SCHRITT 2: Chats migrieren ───────────────────────────────────────────────
print("Schritt 2: Chats in SQLite migrieren...")

with open("export_chats.json", encoding="utf-8") as f:
    chats = json.load(f)

chats_stored = 0
messages_stored = 0
now = "2026-03-27T00:00:00"

for chat in chats:
    chat_id = chat.get("id")
    meta = chat.get("metadata", {}) or {}
    title = meta.get("title", "Importierter Chat") or "Importierter Chat"

    # Datum aus Firestore-Export
    created = meta.get("createdAt") or now
    updated = meta.get("lastUpdated") or created

    # Falls DatetimeWithNanoseconds als String ankam
    if hasattr(created, 'isoformat'):
        created = created.isoformat()
    if hasattr(updated, 'isoformat'):
        updated = updated.isoformat()

    db.execute(
        """INSERT OR IGNORE INTO chats
           (id, title, created_at, last_updated, model_name)
           VALUES (?, ?, ?, ?, ?)""",
        (
            chat_id,
            title,
            str(created),
            str(updated),
            meta.get("model_name", "")
        )
    )
    chats_stored += 1

    # Nachrichten
    for msg in chat.get("messages", []):
        import uuid
        msg_id = msg.get("id") or str(uuid.uuid4())
        role = msg.get("role") or msg.get("author") or "user"
        content = msg.get("content", "")
        timestamp = msg.get("timestamp") or now

        if hasattr(timestamp, 'isoformat'):
            timestamp = timestamp.isoformat()

        db.execute(
            """INSERT OR IGNORE INTO messages
               (id, chat_id, role, content, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (msg_id, chat_id, role, content, str(timestamp))
        )
        messages_stored += 1

db.commit()
print(f"✅ {chats_stored} Chats, {messages_stored} Nachrichten migriert.\n")

# ─── SCHRITT 3: Settings migrieren ────────────────────────────────────────────
print("Schritt 3: Settings migrieren...")

with open("export_settings.json", encoding="utf-8") as f:
    settings = json.load(f)

import json as _json
settings_stored = 0
for key, value in settings.items():
    db.execute(
        """INSERT INTO settings (key, value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET
           value = excluded.value,
           updated_at = excluded.updated_at""",
        (key, _json.dumps(value), now)
    )
    settings_stored += 1

db.commit()
print(f"✅ {settings_stored} Settings migriert.\n")

# ─── ABSCHLUSS ─────────────────────────────────────────────────────────────────
final_count = collection.count()
print("=" * 50)
print(f"🎉 Migration abgeschlossen!")
print(f"   ChromaDB: {final_count} Chunks")
print(f"   SQLite:   {chats_stored} Chats, {messages_stored} Nachrichten")
print(f"   Settings: {settings_stored} Einträge")
print("=" * 50)