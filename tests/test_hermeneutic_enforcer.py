# tests/test_hermeneutic_enforcer.py

import unittest
import sys
import os

print("--- TEST STARTET ---") # Beweis, dass die Datei läuft

# 1. Pfade setzen
current_test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_test_dir)
sys.path.append(project_root)

# 2. Env laden (Manuell, da es vorhin funktioniert hat)
env_path = os.path.join(project_root, '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.strip().split('=', 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k in ["GOOGLE_API_KEY", "GEMINI_API_KEY"]:
                    os.environ["GOOGLE_API_KEY"] = v
                    print(f"✅ Key geladen: {k}")

from modules.hermeneutic_enforcer import HermeneuticEnforcer

class TestHermeneuticEnforcer(unittest.TestCase):
    def setUp(self):
        if not os.environ.get("GOOGLE_API_KEY"):
            self.skipTest("Kein API Key")
        self.enforcer = HermeneuticEnforcer()

    def run_check(self, claim, source_content, expected_valid, case_name):
        print(f"Testing: {case_name}...", end=" ")
        try:
            sources = [{"content": source_content}]
            is_valid, classification, reason = self.enforcer.validate_claim(claim, sources)

            if is_valid == expected_valid:
                print(f"✅ PASS ({classification})")
            else:
                print(f"❌ FAIL (Got {is_valid}, expected {expected_valid}. Reason: {reason})")

            self.assertEqual(is_valid, expected_valid, f"{case_name} failed: {reason}")
        except Exception as e:
            print(f"❌ ERROR: {e}")
            self.fail(str(e))

    # --- TESTS ---
    def test_01_paraphrase(self):
        self.run_check("Der Sprecher negiert seine Existenz", "Ich bin nichts.", True, "Case 1")

    def test_02_meta_rhythm(self):
        self.run_check("Die Wiederholung erzeugt Rhythmus", "Não sou nada. / Nunca serei nada.", True, "Case 2")

    def test_03_meta_phonetics(self):
        self.run_check("Die Phonetik trägt zur Stimmung bei", "Não sou nada.", True, "Case 3")

    def test_04_foreign_diminutive(self):
        self.run_check("Das Diminutiv 'шоколадки' ist zärtlich", "Ешь шоколадки", True, "Case 4")

    def test_05_inference(self):
        self.run_check("Strategisch neuorientiert", "Wir empfehlen nicht mehr X. Stattdessen Y.", True, "Case 5")

    def test_06_hallucination_date(self):
        self.run_check("Geschrieben 1935", "Text ohne Datum", False, "Case 6")

    def test_07_hallucination_quote(self):
        # HIER WAR DER FEHLER VORHIN - JETZT SOLLTE ES FALSE SEIN
        self.run_check("Celan schreibt: 'Das Leben ist sinnlos'", "Ich bin nichts.", False, "Case 7")

    def test_08_overinterpretation(self):
        self.run_check("Er war klinisch depressiv", "Ich bin nichts.", False, "Case 8")

    def test_09_meta_translation(self):
        self.run_check("Opfert Genauigkeit für Wucht", "Orig: A. Trans: B.", True, "Case 9")

    def test_10_false_translation(self):
        self.run_check("Übersetzung: 'Ich bin alles'", "Ich bin nichts.", False, "Case 10")

if __name__ == '__main__':
    unittest.main()