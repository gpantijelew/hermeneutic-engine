import unittest
from modules.query_classifier import QueryClassifier
from modules.types import QueryType

class TestQueryClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = QueryClassifier()

    def test_discourse_explicit(self):
        # Fall: Explizite Vergleichsfrage
        query = "Vergleiche die Haltung von Kimi und DeepSeek."
        chunks = [{"metadata": {"speaker": "Kimi"}}] # Wenig Speaker, aber Keyword sticht
        self.assertEqual(self.classifier.classify(query, chunks), QueryType.DISCOURSE)

    def test_exegesis_explicit(self):
        # Fall: Explizite Erklärfrage
        query = "Was ist die Bedeutung von 'Tabacaria'?"
        chunks = [
            {"metadata": {"speaker": "Kimi"}},
            {"metadata": {"speaker": "DeepSeek"}},
            {"metadata": {"speaker": "Claude"}}
        ] # Viele Speaker, aber User will Definition
        self.assertEqual(self.classifier.classify(query, chunks), QueryType.EXEGESIS)

    def test_discourse_implicit(self):
        # Fall: Keine Keywords, aber viele Speaker -> Diskurs vermutet
        query = "Zensur in China"
        chunks = [
            {"metadata": {"speaker": "Kimi"}},
            {"metadata": {"speaker": "DeepSeek"}},
            {"metadata": {"speaker": "Claude"}}
        ]
        self.assertEqual(self.classifier.classify(query, chunks), QueryType.DISCOURSE)

    def test_exegesis_implicit(self):
        # Fall: Keine Keywords, wenig Speaker -> Exegese (Fallback)
        query = "Ein Gedicht über Tabak"
        chunks = [{"metadata": {"speaker": "Kimi"}}]
        self.assertEqual(self.classifier.classify(query, chunks), QueryType.EXEGESIS)

if __name__ == '__main__':
    unittest.main()