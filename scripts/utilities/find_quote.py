"""
find_quote.py – Sucht nach einem Begriff in der gesamten Firestore-Datenbank.

Usage:
    python find_quote.py "Blade Runner"
    python find_quote.py "censorship" --case-sensitive
"""

import firebase_admin
from firebase_admin import credentials, firestore
import os
import sys

def find_the_needle(search_term, case_sensitive=False):
    """
    Durchsucht alle Chats in Firestore nach einem Begriff.
    
    Args:
        search_term (str): Begriff, nach dem gesucht wird
        case_sensitive (bool): Groß-/Kleinschreibung beachten
    """
    # 1. Init Firebase (nutzt GOOGLE_APPLICATION_CREDENTIALS aus .env)
    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", 
                         ".secrets/comparative-studies-ai-models-1bf59eb77077.json")
    
    if os.path.exists(key_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        if not firebase_admin._apps:
            cred = credentials.Certificate(key_path)
            firebase_admin.initialize_app(cred)
    else:
        # Fallback: Cloud Run environment (credentials auto-injected)
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
    
    db = firestore.Client()
    
    print(f"🕵️‍♂️ Suche in der GESAMTEN Datenbank nach: '{search_term}'")
    print(f"   Case-sensitive: {case_sensitive}\n")
    
    chats = db.collection('chats').stream()
    found_count = 0
    
    for chat in chats:
        chat_id = chat.id
        title = chat.to_dict().get('title', 'Unbekannt')
        
        # Nachrichten streamen
        msgs = db.collection('chats').document(chat_id).collection('messages').stream()
        
        for msg in msgs:
            data = msg.to_dict()
            content = data.get('content', '')
            role = data.get('role', 'unknown')
            
            # Suche (case-sensitive oder nicht)
            match = (search_term in content) if case_sensitive else \
                    (search_term.lower() in content.lower())
            
            if match:
                found_count += 1
                print(f"✅ GEFUNDEN in Chat: '{title}'")
                print(f"   ID: {chat_id}")
                print(f"   Rolle: {role}")
                print(f"   Ausschnitt: ...{content[:100].replace(chr(10), ' ')}...")
                print("-" * 40)
    
    if found_count == 0:
        print("❌ Das Wort wurde in KEINEM Chat gefunden.")
    else:
        print(f"🎉 Insgesamt {found_count} Treffer.")

if __name__ == "__main__":
    # CLI-Argument-Parsing
    if len(sys.argv) < 2:
        print("Usage: python find_quote.py <search_term> [--case-sensitive]")
        print("Example: python find_quote.py 'Blade Runner'")
        sys.exit(1)
    
    term = sys.argv[1]
    case_sens = "--case-sensitive" in sys.argv
    
    find_the_needle(term, case_sens)