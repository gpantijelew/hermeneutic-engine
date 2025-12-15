# reset_vectors.py
import firebase_admin
from firebase_admin import credentials, firestore
import os

def wipe_vectors():
    key_path = "comparative-studies-ai-models-1bf59eb77077.json"
    project_id = "comparative-studies-ai-models"

    print("🔌 Initialisiere Verbindung...")

    # 1. Authentifizierung explizit setzen (WICHTIG für firestore.Client)
    if os.path.exists(key_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        print(f"✅ Environment Variable gesetzt: {key_path}")

        # Firebase Admin Init (falls nötig)
        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
    else:
        print("⚠️ Kein lokaler Key gefunden. Versuche System-Auth...")
        if not firebase_admin._apps:
            firebase_admin.initialize_app()

    # 2. DB Client mit expliziter Projekt-ID
    try:
        db = firestore.Client(project=project_id)
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Konnte Firestore nicht verbinden.\n{e}")
        return

    # 3. Löschvorgang
    col_name = "embeddings"
    print(f"🔥 STARTE BEREINIGUNG VON '{col_name}'...")

    ref = db.collection(col_name)
    deleted_total = 0

    while True:
        # Hole 500 Dokumente
        docs = list(ref.limit(500).stream())
        if not docs:
            break

        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)

        batch.commit()
        deleted_total += len(docs)
        print(f"   ... {len(docs)} Einträge gelöscht (Total: {deleted_total})")

    print(f"\n✅ Bereinigung abgeschlossen. {deleted_total} Vektoren entfernt.")
    print("👉 Jetzt App neu starten, alte Chats löschen und HTML neu importieren.")

if __name__ == "__main__":
    wipe_vectors()