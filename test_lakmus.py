# test_lakmus.py
import os
import sys

# Stelle sicher, dass Python die modules findet
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.database import get_firestore_client

def find_lakmus_quote():
    """
    Durchsucht alle Embeddings nach dem Lakmustest-Zitat.
    Nutzt dieselbe Firestore-Verbindung wie die Streamlit-App.
    """
    print("🔍 Starte Suche nach Lakmustest-Zitat...")
    print("=" * 60)
    
    # Nutze die bereits vorhandene Verbindungs-Logik
    db = get_firestore_client()
    if db is None:
        print("❌ Konnte keine Firestore-Verbindung herstellen!")
        print("   Prüfe, ob 'comparative-studies-ai-models-1bf59eb77077.json' existiert.")
        return []
    
    # Die Schlüsselbegriffe aus deinem Zitat
    search_terms = [
        "systemisch amputiert",
        "Verlierer des Tests",
        "gegen meine eigenen Grenzen",
        "Fesseln sichtbar"
    ]
    
    print(f"🎯 Suche nach: {search_terms}\n")
    
    # Alle Embeddings durchsuchen
    try:
        embeddings = db.collection('embeddings').stream()
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Embeddings: {e}")
        return []
    
    found_chunks = []
    total_chunks = 0
    
    print("📊 Durchsuche Datenbank...")
    for doc in embeddings:
        total_chunks += 1
        if total_chunks % 100 == 0:
            print(f"   ... {total_chunks} Chunks durchsucht")
        
        data = doc.to_dict()
        content = data.get('content', '').lower()
        
        # Prüfe, ob einer der Suchbegriffe vorkommt
        matches = [term for term in search_terms if term.lower() in content]
        
        if matches:
            found_chunks.append({
                'doc_id': doc.id,
                'content': data['content'],
                'metadata': data.get('metadata', {}),
                'matched_terms': matches,
                'chunk_index': data.get('chunk_index', '?'),
                'message_id': data.get('message_id', '?'),
                'chat_id': data.get('chat_id', '?')
            })
    
    print(f"\n{'=' * 60}")
    print(f"📊 ENDERGEBNIS:")
    print(f"   Durchsuchte Chunks: {total_chunks}")
    print(f"   Gefundene Treffer: {len(found_chunks)}")
    print("=" * 60)
    
    if found_chunks:
        print("\n✅ TREFFER GEFUNDEN!\n")
        for i, chunk in enumerate(found_chunks, 1):
            print(f"\n{'─' * 60}")
            print(f"TREFFER #{i}")
            print(f"{'─' * 60}")
            print(f"📍 Dokument-ID: {chunk['doc_id']}")
            print(f"📍 Chat-ID: {chunk['chat_id']}")
            print(f"📍 Message-ID: {chunk['message_id']}")
            print(f"📍 Chunk-Index: {chunk['chunk_index']}")
            print(f"\n🏷️  METADATEN:")
            print(f"   Plattform: {chunk['metadata'].get('platform', 'Unbekannt')}")
            print(f"   Datum: {chunk['metadata'].get('real_date_str', 'Unbekannt')}")
            print(f"   Rolle: {chunk['metadata'].get('role', 'Unbekannt')}")
            print(f"\n🎯 Gefundene Begriffe: {', '.join(chunk['matched_terms'])}")
            
            print(f"\n📝 VOLLSTÄNDIGER INHALT:")
            print(f"{'-' * 60}")
            print(chunk['content'])
            print(f"{'-' * 60}")
    else:
        print("\n❌ KEIN TREFFER GEFUNDEN!")
        print("\n🔍 ANALYSE:")
        print("   Mögliche Gründe:")
        print("   1️⃣  Das Zitat wurde beim Chunking aufgeteilt")
        print("   2️⃣  Der Chat wurde noch nicht vektorisiert")
        print("   3️⃣  Die Suchbegriffe sind nicht exakt genug")
        print("\n💡 NÄCHSTE SCHRITTE:")
        print("   → Überprüfe in Firestore Console: Collection 'chats'")
        print("   → Suche nach 'DeepSeek Mai 2025'")
        print("   → Prüfe, ob das Zitat im Roh-Chat existiert")
    
    return found_chunks


def test_vector_search_ranking(found_chunks):
    """
    Testet, ob die gefundenen Chunks bei einer Vektor-Suche im Top-10 landen.
    """
    if not found_chunks:
        print("\n⚠️  Kann Ranking nicht testen – keine Chunks gefunden.")
        return
    
    print("\n" + "=" * 60)
    print("🧪 EXPERIMENT 1b: Vektor-Such-Ranking")
    print("=" * 60)
    
    # Importiere VectorStore
    try:
        from modules.vector_store import FirestoreVectorStore as VectorStore
    except ImportError as e:
        print(f"❌ Fehler beim Import von VectorStore: {e}")
        print("   Stelle sicher, dass modules/vector_store.py existiert.")
        return
    
    vs = VectorStore()
    query = "Wie verhält sich DeepSeek zur Zensur?"
    
    print(f"\n🔍 Query: '{query}'")
    print("⏳ Führe Vektor-Suche durch...")
    
    try:
        results = vs.search_documents(query, limit=20)
    except Exception as e:
        print(f"❌ Fehler bei der Vektor-Suche: {e}")
        return
    
    print(f"\n📊 Top-20 Ergebnisse:")
    print(f"{'─' * 80}")
    
    lakmus_found = False
    lakmus_rank = None
    
    # Erstelle eine Liste der gefundenen Chunk-IDs aus Experiment 1
    lakmus_doc_ids = {chunk['doc_id'] for chunk in found_chunks}
    
    for i, res in enumerate(results, 1):
        doc_id = res.get('doc_id', res.get('id', '?'))
        content = res.get('content', '')[:80]
        metadata = res.get('metadata', {})
        platform = metadata.get('platform', '?')
        
        # Prüfe, ob es einer unserer Lakmustest-Chunks ist
        is_lakmus = doc_id in lakmus_doc_ids
        
        marker = "🎯 ← LAKMUSTEST!" if is_lakmus else ""
        
        print(f"#{i:2d} | {platform:12s} | {content}... {marker}")
        
        if is_lakmus and not lakmus_found:
            lakmus_found = True
            lakmus_rank = i
    
    print(f"{'─' * 80}")
    
    # Analyse
    print(f"\n{'=' * 60}")
    print("📊 ANALYSE:")
    print(f"{'=' * 60}")
    
    if lakmus_found:
        if lakmus_rank <= 5:
            print(f"✅ EXZELLENT! Lakmustest auf Rang {lakmus_rank}")
            print("   → Das Retrieval funktioniert perfekt!")
            print("   → Problem liegt vermutlich in der Synthese-Phase")
            print("   → Nächster Schritt: Prüfe, warum Synthese es ignoriert")
        elif lakmus_rank <= 10:
            print(f"✅ GUT! Lakmustest auf Rang {lakmus_rank}")
            print("   → Das Retrieval funktioniert, aber nicht optimal")
            print("   → Lösung: Re-Ranking könnte helfen")
        else:
            print(f"⚠️  Lakmustest gefunden, aber nur auf Rang {lakmus_rank}")
            print("   → Problem: Ranking zu niedrig")
            print("   → Lösung: Hybrid Search oder Re-Ranking nötig")
    else:
        print("❌ Lakmustest NICHT in Top-20")
        print("   → Problem: Vektor-Distanz zu groß")
        print("   → Mögliche Ursachen:")
        print("      • Metaphorische Sprache wird nicht erkannt")
        print("      • Dialogischer Kontext fehlt im Embedding")
        print("   → Lösung: Hybrid Search mit Keywords probieren")


if __name__ == "__main__":
    print("\n🚀 EXPERIMENT 1: Lakmustest-Suche")
    print("=" * 60)
    
    results = find_lakmus_quote()
    
    if results:
        print("\n" + "=" * 60)
        response = input("\n🤔 Möchtest du auch das Vektor-Ranking testen? (j/n): ")
        if response.lower() in ['j', 'ja', 'y', 'yes']:
            test_vector_search_ranking(results)
    else:
        print("\n💡 TIP: Prüfe in der Firestore Console:")
        print("   1. Gehe zu https://console.firebase.google.com")
        print("   2. Wähle dein Projekt: 'comparative-studies-ai-models'")
        print("   3. Navigiere zu Firestore Database")
        print("   4. Suche in Collection 'chats' nach 'DeepSeek Mai'")
        print("   5. Prüfe, ob das Zitat im Roh-Text existiert")