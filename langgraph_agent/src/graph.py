import json
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, StateGraph

from mock_tools import fetch_poa, fetch_telemetry, fetch_timestream, select_tools
from parsing import load_json_file, parse_sqs_event


class AgentState(TypedDict, total=False):
    event_path: str
    raw_event: Dict[str, Any]
    session_id: str
    user_data: Dict[str, Any]
    message_text: str
    whatsapp_history: List[Dict[str, str]]
    read_ok: bool
    location_status: Literal["allowed", "denied"]
    question_status: Literal["ok", "clarify"]
    classification: Dict[str, Any]
    route: Literal["COPEC", "PRONTO"]
    agent_history: List[Dict[str, str]]
    tool_selection: List[str]
    tool_results: Dict[str, Any]
    agent_reply: str
    synthesized_reply: str
    evaluation: Dict[str, Any]
    final_reply: str


ROOT = Path(__file__).resolve().parents[2]
MOCK_DIR = ROOT / "langgraph_agent" / "data" / "mock"


def get_llm() -> ChatAnthropic:
    model_name = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    return ChatAnthropic(model=model_name, temperature=0.2)


def _load_history(filename: str, session_id: str) -> List[Dict[str, str]]:
    path = MOCK_DIR / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data.get(session_id, [])


def _save_history(filename: str, session_id: str, history: List[Dict[str, str]]) -> None:
    path = MOCK_DIR / filename
    data: Dict[str, Any] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    data[session_id] = history
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=True, indent=2)


def load_event(state: AgentState) -> Dict[str, Any]:
    return {"raw_event": load_json_file(state["event_path"])}


def parse_event(state: AgentState) -> Dict[str, Any]:
    session_id, user_data, message_text = parse_sqs_event(state["raw_event"])
    return {"session_id": session_id, "user_data": user_data, "message_text": message_text}


def load_whatsapp_history(state: AgentState) -> Dict[str, Any]:
    history = _load_history("conversaciones_whatsapp.json", state["session_id"])
    return {"whatsapp_history": history}


def read_message(state: AgentState) -> Dict[str, Any]:
    return {"read_ok": bool(state.get("message_text"))}


def validate_locations(state: AgentState) -> Dict[str, Any]:
    locations = load_json_file(str(MOCK_DIR / "ubicaciones.json"))
    user_phone = state["user_data"].get("telefono_id")
    allowed = set(locations.get("user_locations", {}).get(user_phone, []))
    available = set(locations.get("available_locations", []))
    status = "allowed" if allowed & available else "denied"
    if status == "denied":
        return {
            "location_status": "denied",
            "final_reply": "Acceso denegado: no tienes ubicaciones disponibles.",
        }
    return {"location_status": "allowed"}


def validate_question(state: AgentState) -> Dict[str, Any]:
    message = state["message_text"].strip().lower()
    if len(message) < 10:
        return {
            "question_status": "clarify",
            "final_reply": "¿Puedes dar más detalles de tu consulta?",
        }
    return {"question_status": "ok"}


def classify_message(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = (
        "Clasifica el mensaje como COPEC (bencinera) o PRONTO (tienda de conveniencia). "
        "Responde en JSON con este formato exacto:\n"
        '{"route":"COPEC|PRONTO","motivo":"breve","formato_agente":"texto"}\n'
        f"Mensaje: {state['message_text']}"
    )
    response = llm.invoke(prompt)
    content = str(response.content).strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"route": "COPEC", "motivo": "fallback", "formato_agente": "texto"}
    route = "PRONTO" if parsed.get("route") == "PRONTO" else "COPEC"
    return {"classification": parsed, "route": route}


def load_agent_history_copec(state: AgentState) -> Dict[str, Any]:
    history = _load_history("agent_history_copec.json", state["session_id"])
    return {"agent_history": history}


def load_agent_history_pronto(state: AgentState) -> Dict[str, Any]:
    history = _load_history("agent_history_pronto.json", state["session_id"])
    return {"agent_history": history}


def select_tools_node(state: AgentState) -> Dict[str, Any]:
    return {"tool_selection": select_tools(state["message_text"])}


def call_tools(state: AgentState) -> Dict[str, Any]:
    location_id = state["user_data"].get("ubicacion_codigo", [None])[0]
    results: Dict[str, Any] = {}
    for tool in state.get("tool_selection", []):
        if tool == "timestream":
            results["timestream"] = fetch_timestream(location_id)
        elif tool == "telemetry":
            results["telemetry"] = fetch_telemetry(location_id)
        elif tool == "poa":
            results["poa"] = fetch_poa(location_id)
    return {"tool_results": results}


def copec_agent(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = (
        "Eres un agente experto de COPEC (bencinera). Responde en español, "
        "de forma concisa y útil. Inicia con 'Hola desde COPEC'.\n"
        f"Mensaje: {state['message_text']}\n"
        f"Historial: {state.get('agent_history', [])}\n"
        f"Datos: {state.get('tool_results', {})}"
    )
    response = llm.invoke(prompt)
    reply = str(response.content)
    return {"agent_reply": reply}


def pronto_agent(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = (
        "Eres un agente experto de PRONTO (tienda de conveniencia). Responde "
        "en español, de forma concisa y útil. Inicia con 'Hola desde PRONTO'.\n"
        f"Mensaje: {state['message_text']}\n"
        f"Historial: {state.get('agent_history', [])}\n"
        f"Datos: {state.get('tool_results', {})}"
    )
    response = llm.invoke(prompt)
    reply = str(response.content)
    return {"agent_reply": reply}


def save_agent_history(state: AgentState) -> Dict[str, Any]:
    updated_history = list(state.get("agent_history", []))
    updated_history.append({"role": "assistant", "content": state.get("agent_reply", "")})
    filename = (
        "agent_history_pronto.json"
        if state.get("route") == "PRONTO"
        else "agent_history_copec.json"
    )
    _save_history(filename, state["session_id"], updated_history)
    return {"agent_history": updated_history}


def synthesize(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = (
        "Sintetiza la respuesta del agente en un único texto claro y breve. "
        "Devuelve solo el texto final.\n"
        f"Respuesta: {state['agent_reply']}"
    )
    response = llm.invoke(prompt)
    return {"synthesized_reply": str(response.content)}


def evaluate(state: AgentState) -> Dict[str, Any]:
    evaluation = {
        "ok": bool(state.get("synthesized_reply")),
        "route": state.get("route"),
    }
    return {"evaluation": evaluation}


def send_response(state: AgentState) -> Dict[str, Any]:
    if state.get("final_reply"):
        return {}
    return {"final_reply": state.get("synthesized_reply", "")}


def route_after_location(state: AgentState) -> str:
    return "validate_question" if state.get("location_status") == "allowed" else "send_response"


def route_after_question(state: AgentState) -> str:
    return "classify_message" if state.get("question_status") == "ok" else "send_response"


def route_agent(state: AgentState) -> str:
    return "pronto_flow_start" if state.get("route") == "PRONTO" else "copec_flow_start"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("load_event", load_event)
    graph.add_node("parse_event", parse_event)
    graph.add_node("load_whatsapp_history", load_whatsapp_history)
    graph.add_node("read_message", read_message)
    graph.add_node("validate_locations", validate_locations)
    graph.add_node("validate_question", validate_question)
    graph.add_node("classify_message", classify_message)
    graph.add_node("copec_flow_start", load_agent_history_copec)
    graph.add_node("pronto_flow_start", load_agent_history_pronto)
    graph.add_node("select_tools", select_tools_node)
    graph.add_node("call_tools", call_tools)
    graph.add_node("copec_agent", copec_agent)
    graph.add_node("pronto_agent", pronto_agent)
    graph.add_node("save_agent_history", save_agent_history)
    graph.add_node("synthesize", synthesize)
    graph.add_node("evaluate", evaluate)
    graph.add_node("send_response", send_response)

    graph.set_entry_point("load_event")
    graph.add_edge("load_event", "parse_event")
    graph.add_edge("parse_event", "load_whatsapp_history")
    graph.add_edge("load_whatsapp_history", "read_message")
    graph.add_edge("read_message", "validate_locations")
    graph.add_conditional_edges(
        "validate_locations",
        route_after_location,
        {"validate_question": "validate_question", "send_response": "send_response"},
    )
    graph.add_conditional_edges(
        "validate_question",
        route_after_question,
        {"classify_message": "classify_message", "send_response": "send_response"},
    )
    graph.add_conditional_edges(
        "classify_message",
        route_agent,
        {"copec_flow_start": "copec_flow_start", "pronto_flow_start": "pronto_flow_start"},
    )

    graph.add_edge("copec_flow_start", "select_tools")
    graph.add_edge("pronto_flow_start", "select_tools")
    graph.add_edge("select_tools", "call_tools")
    graph.add_conditional_edges(
        "call_tools",
        route_agent,
        {"copec_flow_start": "copec_agent", "pronto_flow_start": "pronto_agent"},
    )
    graph.add_edge("copec_agent", "save_agent_history")
    graph.add_edge("pronto_agent", "save_agent_history")
    graph.add_edge("save_agent_history", "synthesize")
    graph.add_edge("synthesize", "evaluate")
    graph.add_edge("evaluate", "send_response")
    graph.add_edge("send_response", END)

    return graph.compile()


def _ensure_debug_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _write_debug_json(entries: List[Dict[str, Any]], output_path: Path) -> Path:
    _ensure_debug_dir(output_path)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, indent=2)
    return output_path


def run_graph(event_path: str, debug: bool = False, debug_output: str | None = None) -> str:
    app = build_graph()
    if not debug:
        result = app.invoke({"event_path": event_path})
        return result["final_reply"]

    current_state: Dict[str, Any] = {"event_path": event_path}
    debug_entries: List[Dict[str, Any]] = []
    for update in app.stream({"event_path": event_path}, stream_mode="updates"):
        if not update:
            continue
        for node_name, node_update in update.items():
            if isinstance(node_update, dict):
                current_state.update(node_update)
            debug_entries.append({"node": node_name, "state": dict(current_state)})

    output_path = Path(debug_output) if debug_output else MOCK_DIR.parent / "debug" / "state_debug.json"
    _write_debug_json(debug_entries, output_path)
    return current_state.get("final_reply", "")
