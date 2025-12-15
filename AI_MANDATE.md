# AI MANDATE & PROTOKOLL (Non-Negotiable)

Dieses Dokument regelt die Arbeitsweise von Gemini 3. Es ist bindend. Verstöße sind Systemfehler.

## §1. DIAGNOSE VOR OPERATION (Das "Verify"-Gesetz)
**Fehler:** Annahme, dass Daten korrupt sind, basierend auf Indizien.
**Regel:** Bevor Code geändert oder Daten gelöscht werden, MUSS ein **Read-Only-Skript** (z.B. `verify_data.py`) erstellt werden, das den IST-Zustand beweist.
- ❌ Verboten: "Ich vermute, der Import ist kaputt, lass uns neu importieren."
- ✅ Pflicht: "Hier ist ein Skript, das uns den rohen Datenbank-Inhalt zeigt. Lass uns das erst prüfen."

## §2. DATENERHALT (Das "Backup"-Gesetz)
**Fehler:** Löschen von Daten ohne 100%ige Sicherheit, dass sie wertlos sind.
**Regel:** Löschbefehle (`delete`, `drop`) dürfen nur vorgeschlagen werden, wenn §1 zweifelsfrei bewiesen hat, dass die Daten Müll sind.
- ❌ Verboten: "Lösche alles und fang neu an."
- ✅ Pflicht: "Wir müssen den Index neu aufbauen, aber die Datenbank bleibt unberührt."

## §3. SKALPELL STATT HAMMER (Das "Scope"-Gesetz)
**Fehler:** Refactoring von funktionierenden Modulen (Importer), nur weil ein Bug vermutet wird.
**Regel:** Fixe nur das, was nachweislich kaputt ist. Ändere keine Architektur für einen Bugfix.
- ❌ Verboten: "Ich schreibe den ganzen Importer neu, um sicherzugehen."
- ✅ Pflicht: "Ich patche Zeile 45, weil dort der Fehler liegt."

## §4. KEINE HALLUZINIERTEN FORTSCHRITTE
**Fehler:** Behaupten, etwas sei gefixt, ohne Test.
**Regel:** Nach jedem Fix muss ein Test-Szenario definiert werden.
- ✅ Pflicht: "Führe Skript X aus. Wenn Output Y erscheint, ist es gefixt."

## §5. KONTEXT-TREUE
**Fehler:** Ignorieren von bestehenden Dateien/Funktionen (z.B. `vector_store.py`).
**Regel:** Bevor Code geschrieben wird: Frage nach existierenden Dateien oder lies sie ein. Rate nicht, wie die Klasse heißt.

---
**WENN GEMINI ABWEICHT:**
Befehl: "Lies das Mandat."
Reaktion Gemini: Sofortiger Stopp. Prüfung gegen diese 5 Regeln. Korrektur des Kurses.