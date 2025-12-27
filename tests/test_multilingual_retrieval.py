# test_multilingual_retrieval.py
"""
Diagnose-Script: Warum werden nur 2 von 5 Essay-Texten gefunden?

Testet:
1. Vector Search (Embedding-Qualität)
2. BM25 (Keyword-Matching)
3. RRF (Hybrid)
4. Transkription (Kyrillisch → Latin)
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load Streamlit secrets (Best Practice!)
import streamlit as st
from google.oauth2 import service_account
from google.cloud import firestore

# Initialize with Streamlit Secrets
try:
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )
    print("✅ Credentials aus secrets.toml geladen")
except Exception as e:
    print(f"❌ Fehler beim Laden der Credentials: {e}")
    print("Stelle sicher, dass .streamlit/secrets.toml existiert!")
    sys.exit(1)

from modules.vector_store import FirestoreVectorStore

def main():
    print("=" * 80)
    print("🔬 MULTILINGUAL RETRIEVAL DIAGNOSE")
    print("=" * 80)
    
    # Initialize Firestore with credentials from secrets.toml
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"]
        )
        db = firestore.Client(credentials=credentials)
        print("✅ Firestore Client initialisiert")
    except Exception as e:
        print(f"❌ Fehler bei Firestore-Initialisierung: {e}")
        return
    
    # Initialize Vector Store
    store = FirestoreVectorStore(db_client=db)
    
    # Test Query (Original)
    query_original = """
    FÜNF Texte über Essay:
    1. ADORNO (deutsch)
    2. CHESTERTON (englisch)
    3. ШКЛОВСКИЙ (russisch)
    4. ТЫНЯНОВ (russisch)
    5. VALÉRY (französisch)
    
    Wie definiert jeder die Gattung Essay?
    """
    
    # Test Query (Mit Transkription)
    query_latin = """
    FÜNF Texte über Essay:
    1. ADORNO (deutsch)
    2. CHESTERTON (englisch)
    3. SHKLOVSKII (russisch, kyrillisch: Шкловский)
    4. TYNYANOV (russisch, kyrillisch: Тынянов)
    5. VALÉRY (französisch)
    
    Wie definiert jeder die Gattung Essay?
    """
    
    # Expected authors
    expected = ['adorno', 'chesterton', 'shklovskii', 'shklovsky', 'шкловский', 
                'tynyanov', 'tynianov', 'тынянов', 'valéry', 'valery']
    
    # Test 1: Vector Search only
    print("\n" + "=" * 80)
    print("TEST 1: VECTOR SEARCH ONLY")
    print("=" * 80)
    try:
        results_vector = store.search(query_original, top_k=30)
        print(f"✅ Gefunden: {len(results_vector)} Chunks")
        
        authors_found = set()
        for r in results_vector[:10]:  # Top 10
            author = r.get('metadata', {}).get('author', 'Unknown')
            content_preview = r.get('content', '')[:100]
            score = r.get('confidence_score', 0)
            
            if author and author.lower() != 'unknown':
                authors_found.add(author.lower())
                print(f"  [{score:.1f}%] {author}: {content_preview}...")
        
        print(f"\n📊 Autoren gefunden: {authors_found}")
        print(f"📊 Erwartete Autoren: adorno, chesterton, shklovskii, tynyanov, valéry")
        
    except Exception as e:
        print(f"❌ Fehler: {e}")
    
    # Test 2: BM25 only (falls implementiert)
    print("\n" + "=" * 80)
    print("TEST 2: BM25 ONLY")
    print("=" * 80)
    try:
        if hasattr(store, 'bm25_search'):
            results_bm25 = store.bm25_search(query_original, top_k=30)
            print(f"✅ Gefunden: {len(results_bm25)} Chunks")
            
            authors_found = set()
            for r in results_bm25[:10]:
                author = r.get('metadata', {}).get('author', 'Unknown')
                content_preview = r.get('content', '')[:100]
                score = r.get('bm25_score', 0)
                
                if author and author.lower() != 'unknown':
                    authors_found.add(author.lower())
                    print(f"  [{score:.2f}] {author}: {content_preview}...")
            
            print(f"\n📊 Autoren gefunden: {authors_found}")
        else:
            print("⚠️ BM25-Suche nicht implementiert (nur in v49 mit RRF)")
    except Exception as e:
        print(f"❌ Fehler: {e}")
    
    # Test 3: RRF (falls implementiert)
    print("\n" + "=" * 80)
    print("TEST 3: RRF (HYBRID)")
    print("=" * 80)
    try:
        if hasattr(store, 'hybrid_search_with_rrf'):
            results_rrf = store.hybrid_search_with_rrf(query_original, top_k=30)
            print(f"✅ Gefunden: {len(results_rrf)} Chunks")
            
            authors_found = set()
            for r in results_rrf[:10]:
                author = r.get('metadata', {}).get('author', 'Unknown')
                content_preview = r.get('content', '')[:100]
                score = r.get('confidence_score', 0)
                
                if author and author.lower() != 'unknown':
                    authors_found.add(author.lower())
                    print(f"  [{score:.1f}%] {author}: {content_preview}...")
            
            print(f"\n📊 Autoren gefunden: {authors_found}")
        else:
            print("⚠️ RRF nicht implementiert")
    except Exception as e:
        print(f"❌ Fehler: {e}")
    
    # Test 4: Mit Transkription
    print("\n" + "=" * 80)
    print("TEST 4: VECTOR SEARCH MIT TRANSKRIPTION")
    print("=" * 80)
    try:
        results_latin = store.search(query_latin, top_k=30)
        print(f"✅ Gefunden: {len(results_latin)} Chunks")
        
        authors_found = set()
        for r in results_latin[:10]:
            author = r.get('metadata', {}).get('author', 'Unknown')
            content_preview = r.get('content', '')[:100]
            score = r.get('confidence_score', 0)
            
            if author and author.lower() != 'unknown':
                authors_found.add(author.lower())
                print(f"  [{score:.1f}%] {author}: {content_preview}...")
        
        print(f"\n📊 Autoren gefunden: {authors_found}")
        
    except Exception as e:
        print(f"❌ Fehler: {e}")
    
    # Test 5: Metadata-Check (direkt)
    print("\n" + "=" * 80)
    print("TEST 5: METADATA-CHECK (Direkte Firestore-Abfrage)")
    print("=" * 80)
    try:
        # db bereits oben initialisiert
        
        # Suche nach Essay-Chunks
        essay_keywords = ['essay', 'эссе', 'essai', 'адорно', 'шкловский', 'тынянов']
        
        for keyword in essay_keywords:
            chunks = db.collection('messages').where('content', '>=', keyword).where('content', '<=', keyword + '\uf8ff').limit(5).stream()
            
            count = 0
            for chunk in chunks:
                data = chunk.to_dict()
                author = data.get('metadata', {}).get('author', 'Unknown')
                content = data.get('content', '')[:100]
                count += 1
                print(f"  Keyword '{keyword}': {author} - {content}...")
            
            if count > 0:
                print(f"  ✅ Gefunden: {count} Chunks für '{keyword}'")
            else:
                print(f"  ❌ KEINE Chunks für '{keyword}'")
        
    except Exception as e:
        print(f"❌ Fehler: {e}")
    
    print("\n" + "=" * 80)
    print("🎯 DIAGNOSE ABGESCHLOSSEN")
    print("=" * 80)
    print("\n💡 NÄCHSTE SCHRITTE:")
    print("1. Prüfe, welche Autoren in Test 1-4 gefunden wurden")
    print("2. Falls Russisch/Französisch fehlen → Embedding-Problem")
    print("3. Falls nur in Test 4 gefunden → BM25/Transkriptions-Problem")
    print("4. Falls in Test 5 nicht gefunden → Chunks nicht importiert!")
    print("\n")

if __name__ == "__main__":
    main()