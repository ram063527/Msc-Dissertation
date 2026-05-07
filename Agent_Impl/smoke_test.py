#
# End-to-end smoke test for the diagnostic agent loop.
#
# Runs a single live trial against the testbed in its current state
# (no fault injected). Verifies the full loop: LM Studio → agent →
# tools → agent → ... → termination.
#
# Prerequisites:
#   - LM Studio running at localhost:1234 with the configured model loaded
#   - Minikube cluster running with all three services deployed
#   - kubectl context pointing at minikube
#
# Run from Agent_Impl/:
#   python smoke_test.py [--condition A|B]
#
# Expected outcomes (any of these = PASS):
#   - terminated=True  : agent called submit_diagnosis
#   - terminated=False : agent hit step limit or produced no tool calls
#     (proves the loop ran and terminated cleanly without exceptions)

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

# Configure logging before importing agent modules so all loggers are captured
logging.basicConfig(
    level=logging.WARNING,           # suppress DEBUG/INFO from langgraph internals
    format="%(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)

# Bump our own modules to DEBUG so we see every node execution
for logger_name in ("agent.nodes", "agent.graph", "tools"):
    logging.getLogger(logger_name).setLevel(logging.DEBUG)

from agent import GRAPH_RECURSION_LIMIT, build_agent, build_initial_state
from config import AGENT_STEP_LIMIT

# Pretty-print helpers

SEP  = "─" * 70
SEP2 = "═" * 70


def _print_message(msg, index: int):
    if isinstance(msg, SystemMessage):
        print(f"  [{index}] SystemMessage ({len(str(msg.content))} chars) — system prompt")

    elif isinstance(msg, HumanMessage):
        print(f"  [{index}] HumanMessage: {str(msg.content)[:120]}")

    elif isinstance(msg, AIMessage):
        tool_calls = msg.tool_calls or []
        if tool_calls:
            calls_str = ", ".join(
                f"{tc['name']}({list(tc['args'].keys())})"
                for tc in tool_calls
            )
            print(f"  [{index}] AIMessage → tool calls: {calls_str}")
        else:
            content_preview = str(msg.content)[:200]
            print(f"  [{index}] AIMessage (no tool calls): {content_preview}")

    elif isinstance(msg, ToolMessage):
        try:
            parsed = json.loads(msg.content)
            status = parsed.get("status", "?")
            # Show a brief data summary
            data_keys = list(parsed.get("data", {}).keys())
            print(f"  [{index}] ToolMessage [{status}] data keys: {data_keys}")
        except (json.JSONDecodeError, AttributeError):
            print(f"  [{index}] ToolMessage: {str(msg.content)[:120]}")

    else:
        print(f"  [{index}] {type(msg).__name__}: {str(msg.content)[:120]}")


def _print_final_state(final_state: dict):
    print(SEP2)
    print("FINAL STATE")
    print(SEP2)
    print(f"  condition   : {final_state['condition']}")
    print(f"  step_count  : {final_state['step_count']}")
    print(f"  terminated  : {final_state['terminated']}")
    print(f"  messages    : {len(final_state['messages'])} total")
    print()
    print("MESSAGE TRACE:")
    for i, msg in enumerate(final_state["messages"]):
        _print_message(msg, i)
    print(SEP2)


def _determine_outcome(final_state: dict) -> tuple[str, bool]:
    """
    Returns (outcome_label, passed).
    passed=True for any clean termination — even without a submission.
    passed=False only if something went wrong structurally.
    """
    if final_state["terminated"]:
        return "SUBMITTED_DIAGNOSIS", True

    last_msg = final_state["messages"][-1]
    if isinstance(last_msg, AIMessage) and not last_msg.tool_calls:
        return "NO_TOOL_CALLS (agent gave up or concluded without submitting)", True

    if final_state["step_count"] >= AGENT_STEP_LIMIT:
        return "STEP_LIMIT_REACHED", True

    return "UNKNOWN_TERMINATION", False


# Main

def run_smoke_test(condition: str):
    print(SEP2)
    print(f"SMOKE TEST — Condition {condition}")
    print(f"Step limit : {AGENT_STEP_LIMIT}")
    print(f"Recursion  : {GRAPH_RECURSION_LIMIT}")
    print(SEP2)

    # --- Build agent ---
    print("\n[1/3] Building agent graph...")
    t0 = time.time()
    graph, system_prompt = build_agent(condition)
    print(f"      Graph compiled in {time.time() - t0:.2f}s")

    # --- Build initial state ---
    print("\n[2/3] Building initial state...")
    initial_state = build_initial_state(condition, system_prompt)
    print(f"      Initial messages: {len(initial_state['messages'])}")
    print(f"      Condition: {initial_state['condition']}")
    print(f"      Step count: {initial_state['step_count']}")
    print(f"      Terminated: {initial_state['terminated']}")

    # --- Run the graph ---
    print(f"\n[3/3] Invoking graph (this will make live LLM + K8s calls)...")
    print(SEP)

    t1 = time.time()
    try:
        final_state = graph.invoke(
            initial_state,
            config={"recursion_limit": GRAPH_RECURSION_LIMIT},
        )
    except Exception as e:
        print(f"\n✗ SMOKE TEST FAILED — unhandled exception during graph.invoke():")
        print(f"  {type(e).__name__}: {e}")
        raise

    elapsed = time.time() - t1
    print(f"\nGraph execution completed in {elapsed:.1f}s")

    # --- Report ---
    _print_final_state(final_state)
    outcome, passed = _determine_outcome(final_state)

    print()
    if passed:
        print(f"✓ SMOKE TEST PASSED — outcome: {outcome}")
    else:
        print(f"✗ SMOKE TEST FAILED — outcome: {outcome}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="End-to-end agent smoke test")
    parser.add_argument(
        "--condition",
        choices=["A", "B"],
        default="B",
        help="Observability condition to test (default: B)",
    )
    args = parser.parse_args()
    run_smoke_test(args.condition)