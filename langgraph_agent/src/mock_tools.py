import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
MOCK_DIR = ROOT / "langgraph_agent" / "data" / "mock"


def _load_mock_json(filename: str) -> Dict[str, Any]:
    path = MOCK_DIR / filename
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def select_tools(message_text: str) -> List[str]:
    normalized = message_text.lower()
    tools: List[str] = []
    if "venta" in normalized or "transaccion" in normalized:
        tools.append("timestream")
    if "stock" in normalized or "quiebre" in normalized:
        tools.append("telemetry")
    if "meta" in normalized or "objetivo" in normalized or "poa" in normalized:
        tools.append("poa")
    if not tools:
        tools.append("timestream")
    return tools


def fetch_timestream(location_id: int) -> Dict[str, Any]:
    data = _load_mock_json("timestream_transacciones.json")
    return data.get(str(location_id), {})


def fetch_telemetry(location_id: int) -> Dict[str, Any]:
    data = _load_mock_json("telemetria_stock.json")
    return data.get(str(location_id), {})


def fetch_poa(location_id: int) -> Dict[str, Any]:
    data = _load_mock_json("poa_2026.json")
    return data.get(str(location_id), {})
