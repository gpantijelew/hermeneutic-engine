import chromadb

client = chromadb.PersistentClient(path='hre_data/chroma')
col = client.get_collection('hre_chunks')

results = col.get(include=['metadatas', 'documents'])
freud_chunks = [
    (results['documents'][i], results['metadatas'][i])
    for i, m in enumerate(results['metadatas'])
    if 'reud' in m.get('chat_title', '')
]

enforcer   = []
meta_hre   = []
inhalt     = []
leer       = []

for doc, meta in freud_chunks:
    if not doc or len(doc.strip()) < 20:
        leer.append((doc, meta))
    elif any(kw in doc for kw in [
        'HALLUCINATION', 'UNSUPPORTED', 'Validierungs-Rate',
        'Enforcer Protokoll', 'Struktur-Check', 'Tiefenprüfung']):
        enforcer.append((doc, meta))
    elif any(kw in doc for kw in [
        'Forschungs-Notiz', 'Synthese\n', '## 💡', 
        'Datum:** ', 'RAG Modus']):
        meta_hre.append((doc, meta))
    else:
        inhalt.append((doc, meta))

print(f"Gesamt Freud-Chunks:          {len(freud_chunks)}")
print(f"Enforcer-Protokoll-Fragmente: {len(enforcer)}")
print(f"HRE-Meta (Synthese-Header):   {len(meta_hre)}")
print(f"Inhaltliche Chunks:           {len(inhalt)}")
print(f"Leer/zu kurz:                 {len(leer)}")

print(f"\n--- Beispiel Enforcer (1. Chunk, 300 Zeichen) ---")
if enforcer:
    print(enforcer[0][0][:300])

print(f"\n--- Beispiel HRE-Meta (1. Chunk, 300 Zeichen) ---")
if meta_hre:
    print(meta_hre[0][0][:300])

print(f"\n--- Beispiel Inhalt (1. Chunk, 300 Zeichen) ---")
if inhalt:
    print(inhalt[0][0][:300])