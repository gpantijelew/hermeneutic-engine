# check_settings.py (KORRIGIERT)
from modules.database import get_firestore_client

db = get_firestore_client()
doc = db.collection('settings').document('global').get()  # ← FIX: 'settings' statt 'global_settings'

if doc.exists:
    settings = doc.to_dict()
    print("=== GLOBAL SETTINGS ===")
    print(f"Model: {settings.get('model_name')}")
    print(f"Temperature: {settings.get('temperature')}")
    print(f"Top-P: {settings.get('top_p')}")
    print(f"\nSystem Instruction (first 1000 chars):")
    print(settings.get('system_instruction', 'NICHT GESETZT')[:1000])
    print("\n[... gekürzt ...]")
else:
    print("⚠️ KEINE SETTINGS GEFUNDEN! (Collection: 'settings', Document: 'global')")