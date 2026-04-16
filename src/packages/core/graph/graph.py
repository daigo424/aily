from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from packages.core.constants import ConversationIntent

from .nodes import (
    handle_booking_intent_node,
    handle_cancel_intent_node,
    handle_cancel_selection_node,
    handle_other_intent_node,
    llm_extraction_node,
)
from .state import BookingState


def _route_entry(state: BookingState) -> str:
    if state["pending_cancel_ids"] and state["text_body"] and state["text_body"].strip().isdigit():
        return "handle_cancel_selection"
    return "llm_extraction"


def _route_intent(state: BookingState) -> str:
    intent = state["intent"]
    if intent == ConversationIntent.CANCEL_RESERVATION:
        return "handle_cancel_intent"
    if intent in {
        ConversationIntent.BOOK_RESERVATION,
        ConversationIntent.UPDATE_BOOKING_REQUEST,
        ConversationIntent.ASK_AVAILABILITY,
    }:
        return "handle_booking_intent"
    return "handle_other_intent"


def build_graph() -> CompiledStateGraph:
    g: StateGraph = StateGraph(BookingState)

    g.add_node("llm_extraction", llm_extraction_node)
    g.add_node("handle_cancel_selection", handle_cancel_selection_node)
    g.add_node("handle_cancel_intent", handle_cancel_intent_node)
    g.add_node("handle_booking_intent", handle_booking_intent_node)
    g.add_node("handle_other_intent", handle_other_intent_node)

    g.add_conditional_edges(
        START,
        _route_entry,
        {
            "handle_cancel_selection": "handle_cancel_selection",
            "llm_extraction": "llm_extraction",
        },
    )
    g.add_conditional_edges(
        "llm_extraction",
        _route_intent,
        {
            "handle_cancel_intent": "handle_cancel_intent",
            "handle_booking_intent": "handle_booking_intent",
            "handle_other_intent": "handle_other_intent",
        },
    )
    g.add_edge("handle_cancel_selection", END)
    g.add_edge("handle_cancel_intent", END)
    g.add_edge("handle_booking_intent", END)
    g.add_edge("handle_other_intent", END)

    return g.compile()


booking_graph: CompiledStateGraph = build_graph()
