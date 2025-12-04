# modules/export.py
import json
import pandas as pd
import io
from typing import List, Dict
from datetime import datetime

def generate_markdown(query: str, answer: str, results: List[Dict], chat_map: Dict, verification_log: Dict = None) -> str:
    """Erstellt einen wissenschaftlich formatierten Markdown-Text inkl. Validierung."""
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    md = f"# Forschungs-Notiz: {query}\n\n"
    md += f"**Datum:** {timestamp}\n\n"

    # 1. Synthese
    md += "## 💡 Synthese\n\n"
    md += f"{answer}\n\n"

    # 2. Enforcer Protokoll (NEU)
    if verification_log:
        md += "## 🛡️ Enforcer Protokoll (Validierung)\n\n"

        # Struktur
        struc = verification_log.get('structure_check', [])
        if not struc:
            md += "- ✅ **Struktur-Check:** Bestanden (Alle Zitate gültig).\n"
        else:
            md += "- ⚠️ **Struktur-Check:** Warnungen:\n"
            for w in struc:
                md += f"  - {w}\n"

        # Inhalt (Deep Check)
        deep = verification_log.get('deep_check', [])
        if deep:
            md += "\n**Tiefenprüfung (Faktencheck):**\n\n"
            for item in deep:
                status_icon = "✅" if item['valid'] else "❌"
                md += f"- {status_icon} *\"{item['sentence']}...\"* → Quelle [{item['source_id']}]\n"
                if not item['valid']:
                    md += f"  - **Diskrepanz:** {item['reason']}\n"
        else:
            md += "\n*(Tiefenprüfung wurde für diesen Export nicht ausgeführt)*\n"

        md += "\n"

    # 3. Quellen
    md += "## 📚 Quellenverzeichnis\n\n"

    for i, res in enumerate(results):
        meta = res.get('metadata', {})
        chat_id = res.get('chat_id', 'unknown')
        chat_title = chat_map.get(chat_id, f"Chat {chat_id[:6]}")

        platform = meta.get('platform', 'Unbekannt')
        date = meta.get('real_date_str', 'o.D.')
        score = res.get('confidence_score', 0)
        content = res.get('content', '').replace('\n', ' ')

        md += f"[^{i+1}]: **{platform}** ({date}). *{chat_title}*. Relevanz: {score:.1f}%.\n"
        md += f"> {content}\n\n"

    return md

def generate_json(query: str, answer: str, results: List[Dict]) -> str:
    """Erstellt einen rohen JSON-Dump für Datenanalysen."""

    # Hilfsfunktion: Konvertiert Firestore-Zeitstempel in Strings
    def json_serial(obj):
        """JSON serializer for objects not serializable by default json code"""
        # Prüfen, ob das Objekt eine isoformat Methode hat (wie datetime)
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        # Fallback: Einfach als String zurückgeben
        return str(obj)

    data = {
        "query": query,
        "generated_answer": answer,
        "timestamp": datetime.now().isoformat(),
        "sources": results
    }

    # Wir nutzen den 'default' Parameter, um unbekannte Objekte (wie Timestamps) zu behandeln
    return json.dumps(data, indent=2, ensure_ascii=False, default=json_serial)

def generate_excel(results: List[Dict], chat_map: Dict) -> bytes:
    """Erstellt eine Excel-Datei mit den Rohdaten der Quellen."""
    rows = []
    for i, res in enumerate(results):
        meta = res.get('metadata', {})
        chat_id = res.get('chat_id', 'unknown')

        row = {
            "Rank": i + 1,
            "Relevance (%)": round(res.get('confidence_score', 0), 1),
            "Role": meta.get('role', 'unknown'),
            "Platform": meta.get('platform', 'Unbekannt'),
            "Date": meta.get('real_date_str', ''),
            "Chat Title": chat_map.get(chat_id, chat_id),
            "Content": res.get('content', ''),
            "Message ID": res.get('message_id', ''),
            "Chat ID": chat_id
        }
        rows.append(row)

    df = pd.DataFrame(rows)

    # In Bytes-Buffer schreiben
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Evidence')

    return output.getvalue()