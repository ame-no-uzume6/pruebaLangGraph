import json
from typing import Any, Dict


def load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_whatsapp_text(sqs_event: Dict[str, Any]) -> str:
    records = sqs_event.get("Records") or []
    if not records:
        raise ValueError("El evento SQS no contiene Records.")

    record_body = records[0].get("body")
    if not record_body:
        raise ValueError("Records[0].body está vacío o no existe.")

    outer_payload = json.loads(record_body)
    event_payload = outer_payload.get("event", {})
    inner_body = event_payload.get("body") or outer_payload.get("body")
    if not inner_body:
        raise ValueError("No se encontró 'body' interno en el payload.")

    if isinstance(inner_body, str):
        inner_payload = json.loads(inner_body)
    elif isinstance(inner_body, dict):
        inner_payload = inner_body
    else:
        raise ValueError("El 'body' interno tiene un tipo no soportado.")

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
