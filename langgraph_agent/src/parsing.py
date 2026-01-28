import json
from typing import Any, Dict, Tuple


def load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_outer_payload(sqs_event: Dict[str, Any]) -> Dict[str, Any]:
    records = sqs_event.get("Records") or []
    if not records:
        raise ValueError("El evento SQS no contiene Records.")

    record_body = records[0].get("body")
    if not record_body:
        raise ValueError("Records[0].body está vacío o no existe.")

    return json.loads(record_body)


def _load_inner_payload(outer_payload: Dict[str, Any]) -> Dict[str, Any]:
    event_payload = outer_payload.get("event", {})
    inner_body = event_payload.get("body") or outer_payload.get("body")
    if not inner_body:
        raise ValueError("No se encontró 'body' interno en el payload.")

    if isinstance(inner_body, str):
        return json.loads(inner_body)
    if isinstance(inner_body, dict):
        return inner_body
    raise ValueError("El 'body' interno tiene un tipo no soportado.")


def extract_whatsapp_text(sqs_event: Dict[str, Any]) -> str:
    outer_payload = _load_outer_payload(sqs_event)
    inner_payload = _load_inner_payload(outer_payload)
    try:
        return (
            inner_payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"][
                "body"
            ]
        )
    except Exception as exc:
        raise ValueError(
            "No se pudo extraer el texto del mensaje de WhatsApp."
        ) from exc


def parse_sqs_event(sqs_event: Dict[str, Any]) -> Tuple[str, Dict[str, Any], str]:
    outer_payload = _load_outer_payload(sqs_event)
    session_id = outer_payload.get("session_id") or "unknown-session"
    user_data = outer_payload.get("user_data") or {}
    message_text = extract_whatsapp_text(sqs_event)
    return session_id, user_data, message_text
