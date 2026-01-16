#!/usr/bin/env python3
"""
Testet ob load_chat_history() die Messages korrekt lädt
"""

import sys
import os

sys.path.insert(0, os.path.abspath('.'))

from google.cloud import firestore
from modules.config import SERVICE_ACCOUNT_KEY_PATH

def get_firestore_client():
    """Initialisiert Firestore"""
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_KEY_PATH
    return firestore.Client(project="comparative-studies-ai-models")

def load_chat_history_standalone(chat_id: str):
    """
    Standalone Version von load_chat_history() - ohne Streamlit
    """
    db = get_firestore_client()
    
    # Messages laden (wie in database.py)
    messages_ref = db.collection('chats').document(chat_id).collection('messages')
    messages = messages_ref.order_by('timestamp').stream()
    
    history = []
    for msg in messages:
        msg_data = msg.to_dict()
        role = msg_data.get('role', 'model')
        content = msg_data.get('content', '')
        
        # Gemini-Format
        history.append({
            'role': role,
            'parts': [{'text': content}]
        })
    
    return history

def test_load_chat_history(chat_id: str):
    print("=" * 80)
    print(f"🧪 TESTE load_chat_history() für Chat: {chat_id}")
    print("=" * 80)
    
    try:
        history = load_chat_history_standalone(chat_id)
        
        print(f"\n✅ Funktion ausgeführt")
        print(f"📊 Ergebnis: {len(history)} Messages")
        
        if not history:
            print("\n❌ PROBLEM: Liste ist LEER!")
            print("   → load_chat_history() findet keine Messages")
            print("   → ABER Firestore HAT 10 Messages (laut inspect)")
            print("\n🔍 Das bedeutet: Problem in load_chat_history() Logik!")
            return False
        
        print("\n📝 Messages (Format-Check):")
        for i, msg in enumerate(history, 1):
            print(f"\n  Message {i}:")
            print(f"    Keys: {list(msg.keys())}")
            print(f"    Role: {msg.get('role', 'FEHLT!')}")
            
            if 'parts' in msg:
                if msg['parts'] and 'text' in msg['parts'][0]:
                    content = msg['parts'][0]['text']
                    print(f"    Content Preview: {content[:80]}...")
                    print(f"    Content Length: {len(content)} chars")
                else:
                    print("    ❌ 'parts' hat falsches Format!")
            else:
                print("    ❌ 'parts' fehlt!")
        
        print("\n" + "=" * 80)
        print("🩺 DIAGNOSE:")
        
        # Prüfe Format
        if all('parts' in msg and 'text' in msg['parts'][0] for msg in history):
            print("✅ Format ist KORREKT (Gemini-Style)")
            print("✅ Sollte in Streamlit angezeigt werden!")
            print("\n💡 Falls Chat trotzdem leer ist:")
            print("   → Prüfe ob Chat in Sidebar-Liste erscheint")
            print("   → Prüfe ob st.session_state.chat_id korrekt gesetzt wird")
            print("   → Prüfe Browser-Cache (Ctrl+Shift+R)")
        else:
            print("❌ Format ist FALSCH!")
            print("   → Streamlit kann Messages nicht anzeigen")
        
        return True
        
    except Exception as e:
        print(f"\n❌ FEHLER beim Laden: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--chat-id', required=True, help='Chat-ID zum Testen')
    
    args = parser.parse_args()
    
    success = test_load_chat_history(args.chat_id)
    
    sys.exit(0 if success else 1)