import chromadb
from collections import Counter

client = chromadb.PersistentClient(path='hre_data/chroma')
col = client.get_collection('hre_chunks')

results = col.get(include=['metadatas'])
titles = [m.get('chat_title', '[unbekannt]') for m in results['metadatas']]
counts = Counter(titles)

print(f"Gesamt-Chunks: {col.count()}")
print(f"\nChunks pro Chat-Titel (gefiltert auf 'Freud'):")
for title, count in sorted(counts.items()):
    if 'freud' in title.lower() or 'Freud' in title:
        print(f"  {count:4d} Chunks — {title}")
print(f"\nAnzahl Freud-Einträge: {sum(1 for t in counts if 'reud' in t)}")