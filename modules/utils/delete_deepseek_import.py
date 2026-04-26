#!/usr/bin/env python3
"""
DeepSeek Import Cleanup Script
Löscht fehlerhaften Import aus Firestore und Vector Store

Usage:
    python delete_deepseek_import.py                    # Interaktiv
    python delete_deepseek_import.py --chat-id CHAT_ID  # Direkt
"""

import sys
import os
from typing import List, Dict

# Path Fix - Gehe zum Projekt-Root (2 Ebenen hoch von modules/utils/)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Direkte Firestore-Imports (ohne Streamlit-Abhängigkeit)
from google.cloud import firestore
from modules.config import SERVICE_ACCOUNT_KEY_PATH

# Optional: Versuche Vector Store zu laden (falls verfügbar)
try:
    from modules.vector_store import FirestoreVectorStore

    VECTOR_STORE_AVAILABLE = True
except ImportError:
    VECTOR_STORE_AVAILABLE = False
    print("⚠️ Warning: Vector Store nicht verfügbar (nicht kritisch)")


# ==============================================================================
# STANDALONE DATABASE FUNCTIONS (ohne Streamlit)
# ==============================================================================


def get_firestore_client_standalone():
    """Initialisiert Firestore-Client OHNE Streamlit."""
    try:
        # Setze Service Account Key
        if os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_KEY_PATH

        db = firestore.Client(project="comparative-studies-ai-models")
        return db
    except Exception as e:
        print(f"❌ Firestore-Verbindungsfehler: {e}")
        return None


def get_chat_list_standalone() -> List[Dict]:
    """Holt Chat-Liste ohne Streamlit."""
    db = get_firestore_client_standalone()
    if not db:
        return []

    try:
        chats = []
        docs = (
            db.collection("chats")
            .order_by("lastUpdated", direction=firestore.Query.DESCENDING)
            .stream()
        )

        for doc in docs:
            data = doc.to_dict()
            chats.append(
                {
                    "id": doc.id,
                    "title": data.get("title", "Ohne Titel"),
                    "lastUpdated": data.get("lastUpdated", data.get("createdAt")),
                }
            )
        return chats
    except Exception as e:
        print(f"❌ Fehler beim Laden der Chat-Liste: {e}")
        return []


def get_raw_chat_messages_standalone(chat_id: str) -> List[Dict]:
    """Holt Messages ohne Streamlit."""
    db = get_firestore_client_standalone()
    if not db:
        return []

    try:
        messages_ref = db.collection("chats").document(chat_id).collection("messages")
        docs = messages_ref.order_by("timestamp").stream()

        messages = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            messages.append(data)
        return messages
    except Exception as e:
        print(f"❌ Fehler beim Laden der Messages: {e}")
        return []


def delete_chat_standalone(chat_id: str) -> bool:
    """Löscht Chat inkl. Messages und Embeddings OHNE Streamlit."""
    db = get_firestore_client_standalone()
    if not db:
        return False

    try:
        # 1. Vektoren löschen (falls Vector Store verfügbar)
        if VECTOR_STORE_AVAILABLE:
            try:
                vector_store = FirestoreVectorStore(db)
                vector_store.delete_chat_embeddings(chat_id)
                print("   ✅ Vektoren gelöscht")
            except Exception as e:
                print(f"   ⚠️ Warnung beim Löschen der Vektoren: {e}")

        # 2. Messages löschen
        messages_ref = db.collection("chats").document(chat_id).collection("messages")
        docs = messages_ref.limit(500).stream()
        deleted = 0

        for doc in docs:
            doc.reference.delete()
            deleted += 1

        if deleted > 0:
            print(f"   ✅ {deleted} Messages gelöscht")
            # Rekursiv, falls mehr als 500
            if deleted == 500:
                return delete_chat_standalone(chat_id)

        # 3. Chat-Dokument löschen
        db.collection("chats").document(chat_id).delete()
        print("   ✅ Chat-Dokument gelöscht")

        return True
    except Exception as e:
        print(f"   ❌ Fehler beim Löschen: {e}")
        return False


def find_deepseek_imports():
    """
    Findet alle DeepSeek-Imports in der Datenbank.

    Returns:
        Liste von Dicts: [{'id': '...', 'title': '...', 'message_count': ...}]
    """
    all_chats = get_chat_list_standalone()
    deepseek_chats = []

    print("🔍 Suche nach DeepSeek-Imports...")

    for chat in all_chats:
        chat_id = chat["id"]
        title = chat["title"]

        # Kriterien für DeepSeek-Import:
        # 1. Titel enthält "DeepSeek" ODER
        # 2. Title ist "Import (DeepSeek)" ODER
        # 3. Title enthält bekannte DeepSeek-Inhalte ODER
        # 4. Titel ist der fehlerhafte Import

        is_deepseek = (
            "deepseek" in title.lower()
            or "import (deepseek)" in title.lower()
            or "vergleich chinesischer ki" in title.lower()
            or "ki-modelle: vergleich" in title.lower()  # Unser fehlerhafter Import
        )

        if is_deepseek:
            # Hole Messages um zu prüfen ob leer
            messages = get_raw_chat_messages_standalone(chat_id)

            deepseek_chats.append(
                {
                    "id": chat_id,
                    "title": title,
                    "message_count": len(messages),
                    "created_at": chat.get("lastUpdated", "Unbekannt"),
                }
            )

    return deepseek_chats


def delete_import_safely(chat_id: str, dry_run: bool = False) -> bool:
    """
    Löscht einen Import sicher (Chat + Messages + Embeddings).

    Args:
        chat_id: Die Chat-ID
        dry_run: Wenn True, nur simulieren

    Returns:
        True bei Erfolg
    """
    try:
        # 1. Zeige was gelöscht wird
        messages = get_raw_chat_messages_standalone(chat_id)
        print(f"\n📋 Chat-ID: {chat_id}")
        print(f"   Messages: {len(messages)}")

        if dry_run:
            print("   🔍 DRY RUN - Keine echten Änderungen")
            return True

        # 2. Lösche mit standalone-Funktion
        print("   🗑️ Lösche Chat, Messages und Embeddings...")

        success = delete_chat_standalone(chat_id)

        if success:
            print("   ✅ Erfolgreich gelöscht!")
            return True
        else:
            print("   ❌ Fehler beim Löschen")
            return False

    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        return False


def interactive_mode():
    """Interaktiver Modus mit Benutzer-Auswahl."""

    print("=" * 80)
    print("🗑️ DEEPSEEK IMPORT CLEANUP TOOL")
    print("=" * 80)

    # Finde DeepSeek-Imports
    deepseek_imports = find_deepseek_imports()

    if not deepseek_imports:
        print("\n✅ Keine DeepSeek-Imports gefunden (oder alle sind OK).")
        return

    print(f"\n📊 Gefunden: {len(deepseek_imports)} DeepSeek-Import(s)\n")

    # Zeige Liste
    for i, imp in enumerate(deepseek_imports, 1):
        status = (
            "❌ LEER"
            if imp["message_count"] == 0
            else f"✅ {imp['message_count']} Messages"
        )

        print(f"{i}. {imp['title']}")
        print(f"   ID: {imp['id']}")
        print(f"   Status: {status}")
        print(f"   Erstellt: {imp['created_at']}")
        print()

    # Benutzer-Auswahl
    print("=" * 80)
    print("Welchen Import möchtest du löschen?")
    print("  - Nummer eingeben (z.B. '1')")
    print("  - 'all' für alle")
    print("  - 'q' zum Abbrechen")

    choice = input("\nDeine Wahl: ").strip().lower()

    if choice == "q":
        print("Abgebrochen.")
        return

    # Sicherheits-Abfrage
    print("\n⚠️ WARNUNG: Diese Aktion ist NICHT rückgängig zu machen!")
    confirm = input("Wirklich löschen? (ja/nein): ").strip().lower()

    if confirm not in ["ja", "yes", "j", "y"]:
        print("Abgebrochen.")
        return

    # Lösche ausgewählte Imports
    if choice == "all":
        print("\n🗑️ Lösche alle DeepSeek-Imports...")
        for imp in deepseek_imports:
            delete_import_safely(imp["id"])
    else:
        try:
            index = int(choice) - 1
            if 0 <= index < len(deepseek_imports):
                imp = deepseek_imports[index]
                delete_import_safely(imp["id"])
            else:
                print("❌ Ungültige Nummer!")
        except ValueError:
            print("❌ Ungültige Eingabe!")

    print("\n✅ Fertig!")


def main():
    """Main Entry Point."""

    import argparse

    parser = argparse.ArgumentParser(
        description="Löscht fehlerhaften DeepSeek-Import aus Firestore"
    )
    parser.add_argument(
        "--chat-id", help="Direkt eine Chat-ID löschen (überspringt interaktiven Modus)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulation (keine echten Änderungen)"
    )
    parser.add_argument(
        "--list", action="store_true", help="Nur DeepSeek-Imports auflisten"
    )

    args = parser.parse_args()

    # Modus: Nur Liste anzeigen
    if args.list:
        imports = find_deepseek_imports()
        if imports:
            print("📋 DeepSeek-Imports:")
            for imp in imports:
                print(
                    f"  - {imp['title']} (ID: {imp['id']}, Messages: {imp['message_count']})"
                )
        else:
            print("✅ Keine DeepSeek-Imports gefunden.")
        return

    # Modus: Direkte Chat-ID
    if args.chat_id:
        print(f"🗑️ Lösche Chat-ID: {args.chat_id}")
        delete_import_safely(args.chat_id, dry_run=args.dry_run)
        return

    # Modus: Interaktiv
    interactive_mode()


if __name__ == "__main__":
    main()
