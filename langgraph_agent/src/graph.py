import os
from typing import Any, Dict, Literal, TypedDict

from langchain_anthropic import ChatAnthropic
from langgraph.graph import END, StateGraph

from parsing import extract_whatsapp_text, load_json_file


class AgentState(TypedDict, total=False):
    event_path: str
    raw_event: Dict[str, Any]
    message_text: str
    route: Literal["COPEC", "PRONTO"]
    agent_reply: str
    final_reply: str


def get_llm() -> ChatAnthropic:
    model_name = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    return ChatAnthropic(model=model_name, temperature=0.2)


def load_event(state: AgentState) -> Dict[str, Any]:
    return {"raw_event": load_json_file(state["event_path"])}


def extract_message(state: AgentState) -> Dict[str, Any]:
    message_text = extract_whatsapp_text(state["raw_event"])
    return {"message_text": message_text}


def classify_intent(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = (
        "Clasifica el mensaje como COPEC (bencinera) o PRONTO (tienda de "
        "conveniencia). Responde SOLO con COPEC o PRONTO.\n"
        f"Mensaje: {state['message_text']}"
    )
    response = llm.invoke(prompt)
    label = str(response.content).upper()
    if "PRONTO" in label:
        route = "PRONTO"
    elif "COPEC" in label:
        route = "COPEC"
    else:
        route = "COPEC"
    return {"route": route}


def copec_agent(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = (
        "Eres un agente experto de COPEC (bencinera). Responde en español, "
        "de forma concisa y útil.\n"
        f"Mensaje: {state['message_text']}"
    )
    response = llm.invoke(prompt)
    return {"agent_reply": str(response.content)}


def pronto_agent(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = (
        "Eres un agente experto de PRONTO (tienda de conveniencia). Responde "
        "en español, de forma concisa y útil.\n"
        f"Mensaje: {state['message_text']}"
    )
    response = llm.invoke(prompt)
    return {"agent_reply": str(response.content)}


def synthesize(state: AgentState) -> Dict[str, Any]:
    llm = get_llm()
    prompt = (
        "Sintetiza la respuesta del agente en un único texto claro y breve. "
        "Devuelve solo el texto final.\n"
        f"Respuesta: {state['agent_reply']}"
    )
    response = llm.invoke(prompt)
    return {"final_reply": str(response.content)}


def route_agent(state: AgentState) -> str:
    return "pronto_agent" if state["route"] == "PRONTO" else "copec_agent"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("load_event", load_event)
    graph.add_node("extract_message", extract_message)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("copec_agent", copec_agent)
    graph.add_node("pronto_agent", pronto_agent)
    graph.add_node("synthesize", synthesize)

    graph.set_entry_point("load_event")
    graph.add_edge("load_event", "extract_message")
    graph.add_edge("extract_message", "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route_agent,
        {"copec_agent": "copec_agent", "pronto_agent": "pronto_agent"},
    )
    graph.add_edge("copec_agent", "synthesize")
    graph.add_edge("pronto_agent", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


def run_graph(event_path: str) -> str:
    app = build_graph()
    result = app.invoke({"event_path": event_path})
    return result["final_reply"]
