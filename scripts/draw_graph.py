"""Generate PNG diagram of the booking graph and save to doc/graph.png."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from langgraph.checkpoint.memory import MemorySaver

from packages.core.graph.graph import build_graph

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "doc", "graph.png")


def main() -> None:
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    graph = build_graph(MemorySaver())
    png_bytes = graph.get_graph().draw_mermaid_png()
    with open(OUTPUT_PATH, "wb") as f:
        f.write(png_bytes)
    print(f"Graph saved to {os.path.normpath(OUTPUT_PATH)}")


if __name__ == "__main__":
    main()