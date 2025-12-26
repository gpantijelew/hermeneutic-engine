# test_preprocessing.py
from modules.preprocessing.chunk_classifier import ChunkClassifier

def test():
    classifier = ChunkClassifier()

    test_chunks = [
        "User: Wie unterscheidet sich Kimi von DeepSeek?",
        "DeepSeek: Im Gegensatz zu Kimi bin ich stärker auf Logik fokussiert. Meine Programmierung verbietet mir Emotionen.",
        "Kimi: Ich denke, Blade Runner ist eine faszinierende Metapher.",
        "Hier ist eine neutrale Analyse der beiden Modelle."
    ]

    print("🔬 TESTE CHUNK CLASSIFIER v47")
    print("="*60)

    for text in test_chunks:
        print(f"\n📄 Input: '{text}'")
        meta = classifier.process_chunk(text)
        print(f"   🏷️  Speaker: {meta.get('model_name')} (Conf: {meta.get('speaker_confidence')})")
        print(f"   🧠 Type:    {meta.get('content_type')}")
        print(f"   🎯 Subjects: {meta.get('subjects')}")
        print("-" * 40)

if __name__ == "__main__":
    test()