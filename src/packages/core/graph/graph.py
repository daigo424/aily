from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from packages.core.constants import ConversationIntent

from .nodes import (
    handle_add_schedule_node,
    handle_list_schedule_node,
    handle_other_intent_node,
    handle_web_search_node,
    llm_extraction_node,
)
from .state import ScheduleState


def _route_intent(state: ScheduleState) -> str:
    intent = state["intent"]
    if intent == ConversationIntent.ADD_SCHEDULE:
        return "handle_add_schedule"
    if intent == ConversationIntent.LIST_SCHEDULE:
        return "handle_list_schedule"
    if state.get("raw_llm_result", {}).get("needs_web_search"):
        return "handle_web_search"
    return "handle_other_intent"


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    g: StateGraph = StateGraph(ScheduleState)

    g.add_node("llm_extraction", llm_extraction_node)
    g.add_node("handle_add_schedule", handle_add_schedule_node)
    g.add_node("handle_list_schedule", handle_list_schedule_node)
    g.add_node("handle_other_intent", handle_other_intent_node)
    g.add_node("handle_web_search", handle_web_search_node)

    g.add_edge(START, "llm_extraction")
    g.add_conditional_edges(
        "llm_extraction",
        _route_intent,
        {
            "handle_add_schedule": "handle_add_schedule",
            "handle_list_schedule": "handle_list_schedule",
            "handle_other_intent": "handle_other_intent",
            "handle_web_search": "handle_web_search",
        },
    )
    g.add_edge("handle_add_schedule", END)
    g.add_edge("handle_list_schedule", END)
    g.add_edge("handle_other_intent", END)
    g.add_edge("handle_web_search", END)

    return g.compile(checkpointer=checkpointer)
