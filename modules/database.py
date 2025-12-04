# modules/database.py
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import uuid
import os
import traceback
import logging
import google.generativeai as genai

# Logging konfigurieren
logger = logging.getLogger(__name__)

# API Key für Titel-Generierung holen
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# ==============================================================================
# 1. BASIS-VERBINDUNG
# ==============================================================================
@st.cache_resource
def get_firestore_client():
    """Initialisiert Firestore-Client mit intelligenter Credential-Erkennung."""
    try:
        # Prüfe, ob ein lokaler Master-Key existiert
        master_key_path = "comparative-studies-ai-models-1bf59eb77077.json" 

        if os.path.exists(master_key_path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = master_key_path
            # Nur loggen, nicht st.write nutzen, um UI nicht zu spammen
            logger.info("Lokal: Verwende Master Service-Account-Key")
        else:
            logger.info("Cloud: Verwende Application Default Credentials")

        db = firestore.Client(project="comparative-studies-ai-models")
        return db

    except Exception as e:
        st.error(f"🔥 Firestore-Verbindungsfehler: {e}")
        st.error(f"Traceback: {traceback.format_exc()}")
        return None

# ==============================================================================
# 2. CHAT-MANAGEMENT (Erstellen, Speichern, Löschen)
# ==============================================================================

def create_chat_in_firestore(title="Neuer Chat"):
    db = get_firestore_client()
    if db is None: return None
    try:
        chat_ref = db.collection('chats').document()
        chat_ref.set({
            'title': title, 
            'createdAt': firestore.SERVER_TIMESTAMP, 
            'lastUpdated': firestore.SERVER_TIMESTAMP
        })
        logger.info(f"✅ Chat erstellt: ID={chat_ref.id}, Title={title}")
        return chat_ref.id
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen des Chats: {e}")
        st.error(f"❌ Fehler beim Erstellen des Chats: {e}")
        return None

def save_message(chat_id, author, content):
    db = get_firestore_client()
    if db is None: return False
    try:
        messages_ref = db.collection('chats').document(chat_id).collection('messages')
        messages_ref.add({
            'author': author, 
            'content': content, 
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        # Update des Zeitstempels im Haupt-Dokument
        db.collection('chats').document(chat_id).update({
            'lastUpdated': firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern der Nachricht: {e}")
        return False

def delete_chat(chat_id):
    db = get_firestore_client()
    if db is None: return False
    try:
        # 1. Alle Nachrichten löschen (Batch-Delete wäre besser, aber rekursiv geht auch)
        messages_ref = db.collection('chats').document(chat_id).collection('messages')
        docs = messages_ref.limit(500).stream()
        deleted = 0
        for doc in docs:
            doc.reference.delete()
            deleted += 1

        if deleted > 0:
            # Rekursiv aufrufen, falls mehr als 500 Nachrichten da waren
            return delete_chat(chat_id)

        # 2. Chat-Dokument selbst löschen
        db.collection('chats').document(chat_id).delete()
        return True
    except Exception as e:
        st.error(f"Fehler beim Löschen des Chats: {e}")
        return False

def rename_chat(chat_id, new_title):
    db = get_firestore_client()
    if db is None: return False
    try:
        db.collection('chats').document(chat_id).update({'title': new_title})
        return True
    except Exception as e:
        st.error(f"Fehler beim Umbenennen: {e}")
        return False

# ==============================================================================
# 3. DATEN-ABRUF (Laden für UI)
# ==============================================================================

def get_chat_list():
    db = get_firestore_client()
    if db is None: return []
    try:
        chats = []
        docs = db.collection('chats').order_by('lastUpdated', direction=firestore.Query.DESCENDING).stream()
        for doc in docs:
            data = doc.to_dict()
            chats.append({
                'id': doc.id, 
                'title': data.get('title', 'Ohne Titel'), 
                'lastUpdated': data.get('lastUpdated', data.get('createdAt'))
            })
        return chats
    except Exception as e:
        st.error(f"❌ Fehler beim Laden der Chat-Liste: {e}")
        return []

def load_chat_history(chat_id):
    db = get_firestore_client()
    if db is None: return []
    try:
        messages = db.collection('chats').document(chat_id).collection('messages').order_by('timestamp').stream()
        history = []
        for msg in messages:
            msg_data = msg.to_dict()
            role = 'user' if msg_data.get('author') == 'user' else 'model'
            history.append({'role': role, 'parts': [{'text': msg_data.get('content', '')}]})
        return history
    except Exception as e:
        st.error(f"Fehler beim Laden der Chat-Historie: {e}")
        return []

# ==============================================================================
# 4. SETTINGS & KI-HELFER
# ==============================================================================

def generate_and_update_title(chat_id, history):
    """Generiert einen Titel mit Gemini Flash Lite."""
    if not GEMINI_API_KEY:
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)

        # Nimm die ersten paar Nachrichten für den Kontext
        conversation_text = ""
        for msg in history[:4]:
            role = msg.get('role', '')
            text = ""
            if 'parts' in msg and msg['parts']:
                text = msg['parts'][0].get('text', '')
            elif 'content' in msg:
                text = msg['content']
            conversation_text += f"{role}: {text}\n"

        prompt = f"Fasse den folgenden Gesprächsanfang in einem prägnanten Titel mit maximal 5 Wörtern zusammen. Antworte NUR mit dem Titel. Gespräch:\n---\n{conversation_text}\n---\nTitel:"

        model = genai.GenerativeModel(model_name="gemini-2.0-flash-lite-001") # Nutze das schnelle Modell
        title_response = model.generate_content(prompt)
        new_title = title_response.text.strip().replace('"', '')

        db = get_firestore_client()
        if db:
            db.collection('chats').document(chat_id).update({'title': new_title})

        if 'title_generated' not in st.session_state:
            st.session_state.title_generated = True

        return new_title
    except Exception as e:
        logger.warning(f"Titelgenerierung fehlgeschlagen: {e}")
        return None

def load_global_settings(default_settings):
    db = get_firestore_client()
    if db is None: return default_settings
    try:
        settings_ref = db.collection('settings').document('global')
        settings = settings_ref.get()
        if settings.exists:
            data = settings.to_dict()
            return {
                'model_name': data.get('model_name', default_settings.get('model_name')),
                'temperature': data.get('temperature', default_settings.get('temperature')),
                'top_p': data.get('top_p', default_settings.get('top_p')),
                'system_instruction': data.get('system_instruction', default_settings.get('system_instruction')),
                'use_search': data.get('use_search', default_settings.get('use_search')),
                'debug_mode': data.get('debug_mode', default_settings.get('debug_mode'))
            }
        return default_settings
    except Exception as e:
        return default_settings

def save_global_settings(model_name, temperature, top_p, system_instruction, use_search, debug_mode):
    db = get_firestore_client()
    if db is None: return False
    try:
        settings_ref = db.collection('settings').document('global')
        settings_ref.set({
            'model_name': model_name,
            'temperature': temperature, 
            'top_p': top_p, 
            'system_instruction': system_instruction, 
            'use_search': use_search, 
            'debug_mode': debug_mode, 
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        st.error(f"❌ Fehler beim Speichern: {e}")
        return False