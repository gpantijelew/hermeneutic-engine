# modules/export.py
"""
Export-Funktionen für die Hermeneutic Reconstruction Engine.

PHILOSOPHIE:
- Wissenschaftliche Transparenz: Zeige nicht nur Antworten, sondern auch den Weg dorthin
- Multiple Formate: Markdown (human), JSON (machine), Excel (analysis)
- Enforcer-Integration: Dokumentiere Validierung explizit

ÄNDERUNGSHISTORIE:
- v58: Keine Änderung — ENGINE_VERSION aus config.py übernimmt automatisch
- v56: ENGINE_VERSION aus config.py importiert statt hartcodiertem String
- v55: generate_chat_markdown() hinzugefügt für Chat-Export
- v49: Initiale Version mit Markdown/JSON/Excel
"""

import json
import uuid
import pandas as pd
import io
from typing import List, Dict, Optional
from datetime import datetime

from modules.config import MODEL_SYNTHESIS, LLM_BACKEND, LM_STUDIO_MODEL, ENGINE_VERSION


def _get_backend_model() -> str:
    """Gibt das tatsächlich genutzte Modell basierend auf Backend zurück."""
    if LLM_BACKEND == "vertex":
        from modules.config import VERTEX_MODEL
        return VERTEX_MODEL
    elif LLM_BACKEND == "openai":
        from modules.config import OPENAI_MODEL
        return OPENAI_MODEL
    else:
        return LM_STUDIO_MODEL


def generate_markdown(
    query: str,
    answer: str,
    results: List[Dict],
    chat_map: Dict,
    verification_log: Optional[Dict] = None,
    pipeline_trace: Optional[Dict] = None,
) -> str:
    """
    Erstellt einen wissenschaftlich formatierten Markdown-Text für RAG-Analysen.

    Für: Analyse-Fenster (vollständiger RAG-Workflow mit Quellen & Enforcer)

    Args:
        query: User-Frage
        answer: Generierte Synthese
        results: Liste der gefundenen Quellen (mit metadata, confidence_score, etc.)
        chat_map: Dict {chat_id: title} für Quellenverzeichnis
        verification_log: Optional, Enforcer-Protokoll (structure_check, deep_check)

    Returns:
        Formatierter Markdown-String
    """
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    analysis_id = str(uuid.uuid4())[:8]

    # --- A.1 Reproducibility Manifest + A.2 Deterministic Pipeline ---
    from modules.config import DOMAIN_PROFILES, DOMAIN_ANALYSIS
    profile = DOMAIN_PROFILES.get(DOMAIN_ANALYSIS, {})

    # --- P3: Enforcer-Score + Domain-Profile in Export-Header ---
    enforcer_score = None
    if verification_log:
        deep = verification_log.get("deep_check", [])
        if deep:
            valid_count = sum(1 for item in deep if item.get("valid", False))
            total_count = len(deep)
            enforcer_score = (valid_count / total_count * 100) if total_count > 0 else 0
    # --- /P3 ---

    md = "---\n"
    md += "reproducibility_manifest:\n"
    md += f"  analysis_id:      {analysis_id}\n"
    md += f"  timestamp:        {datetime.now().isoformat()}\n"
    md += f"  engine_version:   {ENGINE_VERSION}\n"
    md += f"  query:            \"{query.replace(chr(34), chr(39))}\"\n"
    md += f"  model_synthesis:  {_get_backend_model()}\n"
    md += f"  deterministic_mode: True (Domain: {DOMAIN_ANALYSIS})\n"
    md += f"  analysis_domain:  {DOMAIN_ANALYSIS}\n"
    md += f"  analysis_temperature: {profile.get('temperature', 'default')}\n"
    md += f"  analysis_seed: {profile.get('seed', 'none')}\n"
    md += f"  analysis_top_p: {profile.get('top_p', 'default')}\n"
    md += f"  enforcer_score: {enforcer_score:.1f}%\n" if enforcer_score is not None else "  enforcer_score: N/A (Tiefenprüfung nicht ausgeführt)\n"

    if pipeline_trace:
        md += f"  intent:           {pipeline_trace.get('intent', 'N/A')}\n"
        md += f"  semantic_intent:  {pipeline_trace.get('semantic_intent', 'N/A')}\n"
        md += f"  threshold:        {pipeline_trace.get('threshold', 'N/A')}\n"
        md += f"  query_type:       {pipeline_trace.get('query_type', 'N/A')}\n"
        md += f"  essence_parity:   {pipeline_trace.get('essence_parity', False)}\n"
        md += f"  chunks_used:      {pipeline_trace.get('chunks_retrieved', 0)}\n"
        md += f"  reranker_total:   {pipeline_trace.get('reranker_total', 0)}\n"
        md += f"  reranker_passed:  {pipeline_trace.get('reranker_passed', 0)}\n"
        md += f"  reranker_rejected:{pipeline_trace.get('reranker_rejected', 0)}\n"
        md += f"  reranker_avg:     {pipeline_trace.get('reranker_avg', 'N/A')}\n"
        md += f"  reranker_failed:  {pipeline_trace.get('reranker_failed', False)}\n"
        # v57: Extraktions-Fehler im Manifest sichtbar machen
        _ext_fail = pipeline_trace.get('extraction_failures', [])
        if _ext_fail:
            _failed_ids = [f"[{f['source_id']}]" for f in _ext_fail if f.get('reason') == 'json_parse_failed']
            if _failed_ids:
                md += f"  extraction_failures: {', '.join(_failed_ids)} (JSON-Parsing-Fehler)\n"
    else:
        md += "  pipeline_trace:   null\n"

    md += "---\n\n"

    md += f"# Forschungs-Notiz: {query}\n\n"
    md += f"**Datum:** {timestamp}\n\n"

    # 1. Synthese
    md += "## 💡 Synthese\n\n"
    md += f"{answer}\n\n"

    # 2. Enforcer Protokoll (falls vorhanden)
    if verification_log:
        md += "## 🛡️ Enforcer Protokoll (Validierung)\n\n"

        # Struktur-Check
        struc = verification_log.get("structure_check", [])
        if not struc:
            md += "- ✅ **Struktur-Check:** Bestanden (Alle Zitate gültig).\n"
        else:
            md += "- ⚠️ **Struktur-Check:** Warnungen:\n"
            for w in struc:
                md += f"  - {w}\n"

        # Tiefenprüfung (Deep Check) mit Summary-Stats
        deep = verification_log.get("deep_check", [])
        if deep:
            # NEU v55: Summary-Statistik
            valid_count = sum(1 for item in deep if item.get("valid", False))
            total_count = len(deep)
            pass_rate = (valid_count / total_count * 100) if total_count > 0 else 0

            md += f"\n**Validierungs-Rate:** {valid_count}/{total_count} Aussagen bestätigt ({pass_rate:.1f}%)\n\n"
            md += "**Tiefenprüfung (Faktencheck):**\n\n"

            for item in deep:
                status_icon = "✅" if item.get("valid", False) else "❌"
                sentence = item.get("sentence", "")[:100]  # Truncate lange Sätze
                md += f'- {status_icon} *"{sentence}..."* → Quelle [{item.get("source_id", "?")}]\n'

                if not item.get("valid", False):
                    md += f"  - **Diskrepanz:** {item.get('reason', 'Unbekannt')}\n"
        else:
            md += "\n*(Tiefenprüfung wurde für diesen Export nicht ausgeführt)*\n"

        md += "\n"

    # 3. Quellenverzeichnis
    md += "## 📚 Quellenverzeichnis\n\n"

    for i, res in enumerate(results, 1):
        meta = res.get("metadata", {})
        chat_id = res.get("chat_id", "unknown")

        # Metadaten extrahieren
        chat_title = chat_map.get(chat_id, f"Chat {chat_id[:6]}")
        platform = meta.get("platform", "Unbekannt")
        date = meta.get("real_date_str", "o.D.")
        score = res.get("confidence_score", 0)

        # Content (volle Chunks für spätere Arbeit, wie gewünscht)
        content = res.get("content", "").replace("\n", " ")

        # Quelle formatieren
        md += f"**[{i}] {platform}** ({date}). *{chat_title}*. Relevanz: {score:.1f}%.\n\n"
        md += f"> {content}\n\n"

    return md


def generate_markdown_from_record(record: Dict) -> str:
    """
    A.3: Rekonstruiert Markdown aus einem DB-Analyse-Record.

    Nutzt nur die persistierten Felder — kein Zugriff auf Streamlit-State
    oder aktuelle Pipeline-Trace. Für Lazy-Loading aus der DB gedacht.

    Args:
        record: Dict aus get_analysis_by_id() (alle Felder der analyses-Tabelle)

    Returns:
        Markdown-String mit Manifest + Synthese (kein Quellenverzeichnis,
        da Chunks nicht in DB persistiert werden).
    """
    from modules.config import DOMAIN_PROFILES, DOMAIN_ANALYSIS

    analysis_id = record.get("analysis_id", "unknown")
    timestamp = record.get("timestamp", datetime.now().isoformat())
    query = record.get("query", "")
    answer = record.get("answer_text", "")
    intent = record.get("intent", "N/A")
    semantic_intent = record.get("semantic_intent", "N/A")
    model = record.get("model", "unknown")
    temperature = record.get("temperature")
    seed = record.get("seed")
    top_p = record.get("top_p")
    domain = record.get("analysis_domain", DOMAIN_ANALYSIS)

    profile = DOMAIN_PROFILES.get(domain, {})

    # --- P3: Enforcer-Score aus DB-Record rekonstruieren ---
    enforcer_score = record.get("enforcer_score")
    # --- /P3 ---

    # Manifest aus Record rekonstruieren
    md = "---\n"
    md += "reproducibility_manifest:\n"
    md += f"  analysis_id:      {analysis_id}\n"
    md += f"  timestamp:        {timestamp}\n"
    md += f"  engine_version:   {ENGINE_VERSION}\n"
    md += f"  query:            \"{query.replace(chr(34), chr(39))}\"\n"
    md += f"  model_synthesis:  {model}\n"
    md += f"  deterministic_mode: True (Domain: {domain})\n"
    md += f"  analysis_domain:  {domain}\n"
    md += f"  analysis_temperature: {temperature if temperature is not None else profile.get('temperature', 'default')}\n"
    md += f"  analysis_seed: {seed if seed is not None else profile.get('seed', 'none')}\n"
    md += f"  analysis_top_p: {top_p if top_p is not None else profile.get('top_p', 'default')}\n"
    md += f"  enforcer_score: {enforcer_score:.1f}%\n" if enforcer_score is not None else "  enforcer_score: N/A (nicht persistiert)\n"
    md += f"  intent:           {intent}\n"
    md += f"  semantic_intent:  {semantic_intent}\n"
    md += "  pipeline_trace:   (rekonstruiert aus DB-Record)\n"

    cited_ids = record.get("cited_document_ids", [])
    if cited_ids:
        md += f"  cited_documents:  {len(cited_ids)}\n"
    md += "---\n\n"

    md += f"# Forschungs-Notiz: {query}\n\n"
    md += f"**Datum:** {timestamp[:16] if len(timestamp) >= 16 else timestamp}\n\n"

    md += "## 💡 Synthese\n\n"
    md += f"{answer}\n\n"

    if cited_ids:
        md += "## 📚 Zitierte Dokumente\n\n"
        for cid in cited_ids:
            md += f"- [{cid}]\n"
        md += "\n"

    md += "---\n\n*(Vollständiges Quellenverzeichnis mit Chunk-Inhalten war zum Zeitpunkt der Persistenz nicht in der DB gespeichert.)*\n"

    return md


def generate_chat_markdown(
    messages: List[Dict], chat_title: str = "Chat-Protokoll"
) -> str:
    """
    Erstellt einen Markdown-Export für Chat-Konversationen (mit/ohne RAG).

    Für: Chat-Fenster (Lite-Export ohne Quellen-Details)

    v55: Minimal-Version – voller Chat-Verlauf, keine RAG-Metadaten.
    TODO v51: Integration mit rag_metadata aus Firestore für vollständige Persistenz.

    Args:
        messages: Chat-Historie (Streamlit format: {"role": "...", "parts": [{"text": "..."}]})
        chat_title: Titel aus Firestore

    Returns:
        Formatierter Markdown-String
    """
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")

    md = f"# {chat_title}\n\n"
    md += f"**Export-Datum:** {timestamp}\n"
    md += f"**Anzahl Nachrichten:** {len(messages)}\n\n"
    md += "---\n\n"

    for i, msg in enumerate(messages, 1):
        role = msg.get("role", "user")

        # Content extrahieren (robust gegen verschiedene Formate)
        parts = msg.get("parts", [])
        if parts and isinstance(parts, list) and len(parts) > 0:
            content = parts[0].get("text", "")
        else:
            content = "*(Keine Nachricht)*"

        # Header mit Icons
        if role == "user":
            header = f"### 👤 Nachricht {i} (User)"
        else:
            header = f"### 🤖 Nachricht {i} (Assistent)"

        md += f"{header}\n\n{content}\n\n---\n\n"

    # TODO v51: Wenn rag_metadata in Message vorhanden, Quellen anhängen:
    # if msg.get('rag_metadata'):
    #     sources = msg['rag_metadata']['sources']
    #     md += "\n**Quellen für diese Antwort:**\n\n"
    #     for s in sources:
    #         md += f"- [{s['source_id']}] {s['metadata']['chat_title']}\n"

    return md


def generate_json(query: str, answer: str, results: List[Dict]) -> str:
    """
    Erstellt einen rohen JSON-Dump für Datenanalysen.

    TODO v51: Metadaten hinzufügen (Engine-Version, Models, Reproduzierbarkeit)

    Args:
        query: User-Frage
        answer: Generierte Antwort
        results: Quellen-Liste

    Returns:
        JSON-String
    """

    # Hilfsfunktion: Konvertiert Firestore-Zeitstempel & Vektoren
    def json_serial(obj):
        """JSON serializer for objects not serializable by default"""
        if isinstance(obj, datetime):
            return obj.isoformat()

        # FIX: Firestore Vector handling
        if hasattr(obj, "__class__") and "Vector" in obj.__class__.__name__:
            try:
                # Try to extract vector values (depends on Firestore version)
                if hasattr(obj, "to_map_value"):
                    return str(obj.to_map_value())
                elif hasattr(obj, "_values"):
                    return list(obj._values)
                else:
                    return str(obj)  # Fallback
            except Exception:
                return str(obj)

        # Fallback für unbekannte Typen
        return str(obj)

    data = {
        "query": query,
        "generated_answer": answer,
        "timestamp": datetime.now().isoformat(),
        "sources": results,
    }

    # TODO v51: Erweitern mit:
    # "metadata": {
    #     "engine_version": "v55",
    #     "synthesis_model": MODEL_SYNTHESIS,
    #     "enforcer_model": MODEL_ENFORCER,
    #     "retrieval_strategy": "hermeneutic"
    # }

    return json.dumps(data, indent=2, ensure_ascii=False, default=json_serial)


def generate_excel(results: List[Dict], chat_map: Dict) -> bytes:
    """
    Erstellt eine Excel-Datei mit den Rohdaten der Quellen.

    TODO v51: Enforcer-Status als Spalte hinzufügen (für Filterung)

    Args:
        results: Quellen-Liste
        chat_map: Dict {chat_id: title}

    Returns:
        Excel-Datei als Bytes
    """
    rows = []

    for i, res in enumerate(results, 1):
        meta = res.get("metadata", {})
        chat_id = res.get("chat_id", "unknown")

        row = {
            "Rank": i,
            "Relevance (%)": round(res.get("confidence_score", 0), 1),
            "Role": meta.get("role", "unknown"),
            "Platform": meta.get("platform", "Unbekannt"),
            "Date": meta.get("real_date_str", ""),
            "Chat Title": chat_map.get(chat_id, chat_id),
            "Content": res.get("content", ""),
            "Message ID": res.get("message_id", ""),
            "Chat ID": chat_id,
        }

        # TODO v51: Enforcer-Spalte hinzufügen
        # row["Enforcer Status"] = "✅ Valid" / "❌ Invalid" / "N/A"

        rows.append(row)

    df = pd.DataFrame(rows)

    # In Bytes-Buffer schreiben
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Evidence")

    return output.getvalue()
