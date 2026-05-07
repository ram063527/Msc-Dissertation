# Node factory functions for the diagnostic agent graph.
#
# Both nodes are constructed via factory functions that close over
# the model and tools. The factories are called once in graph.py;
# the returned callables are registered as graph nodes.
#

import json
import logging
from typing import Callable

from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

from agent.state import AgentState

logger = logging.getLogger(__name__)

# agent_node factory


def make_agent_node(model_with_tools: Runnable) -> Callable:
    """
    Factory that returns the agent_node callable.

    The returned node calls the LLM with the full message history and
    appends the resulting AIMessage to state.
    """

    def agent_node(state: AgentState) -> dict:
        """
        Call the LLM with the current message history.

        The LLM returns either:
          - An AIMessage with non-empty tool_calls → agent wants to invoke tools
          - An AIMessage with empty tool_calls → agent is done (or gave up)

        The should_continue edge in graph.py inspects tool_calls to decide
        which case applies.

        Errors from the LLM are allowed to propagate — the harness owns
        session-level error handling.
        """
        logger.debug(f"[agent_node] condition={state['condition']} "
                     f"step={state['step_count']} "
                     f"messages={len(state['messages'])}")

        response: AIMessage = model_with_tools.invoke(state["messages"])

        logger.debug(
            f"[agent_node] response tool_calls={len(response.tool_calls)} "
            f"content_length={len(str(response.content))}")

        # Return only the messages key — add_messages reducer appends response.
        return {"messages": [response]}

    return agent_node


# tools_node factory


def make_tools_node(tools: list[BaseTool]) -> Callable:
    """
    Factory that returns the tools_node callable.

    The returned node:
      1. Delegates tool execution to LangGraph's ToolNode (handles parallel
         calls, error catching, and ToolMessage construction).
      2. Increments step_count by 1.
      3. Sets terminated=True if submit_diagnosis returned status="success".

    """
    # Instantiate LangGraph's prebuilt ToolNode once.
    # ToolNode handles: tool lookup by name, parallel execution of multiple
    # tool calls in a single AIMessage, exception catching per tool call,
    # and ToolMessage construction with correct tool_call_id linkage.

    _tool_node = ToolNode(tools)

    def tools_node(state: AgentState) -> dict:
        """
        Execute all tool calls from the last AIMessage.

        After execution, check if submit_diagnosis succeeded and
        increment the step counter.
        """
        logger.debug(f"[tools_node] condition={state['condition']} "
                     f"step={state['step_count']} — executing tool calls")

        # Delegate to ToolNode for execution.
        # Returns a dict with key "messages" containing list[ToolMessage].
        tool_result: dict = _tool_node.invoke(state)
        new_tool_messages = tool_result.get("messages", [])

        # --- Termination detection ---
        # Build a lookup of tool_call_id → tool_name from the last AIMessage.
        # This lets us identify which ToolMessage corresponds to submit_diagnosis
        # without relying solely on content parsing.
        last_ai_message: AIMessage = state["messages"][-1]
        call_id_to_name: dict[str, str] = {
            tc["id"]: tc["name"]
            for tc in last_ai_message.tool_calls
        }

        terminated = state["terminated"]  # carry forward if already True

        for tool_msg in new_tool_messages:
            tool_name = call_id_to_name.get(tool_msg.tool_call_id, "")

            if tool_name == "submit_diagnosis":
                terminated = _check_submission_succeeded(tool_msg.content)
                if terminated:
                    logger.info(f"[tools_node] submit_diagnosis succeeded — "
                                f"session will terminate after this step.")

        new_step_count = state["step_count"] + 1

        logger.debug(f"[tools_node] step_count now {new_step_count} "
                     f"terminated={terminated}")

        return {
            "messages": new_tool_messages,
            "step_count": new_step_count,
            "terminated": terminated,
        }

    return tools_node


# Internal helpers


def _check_submission_succeeded(content) -> bool:
    """
    Parse ToolMessage content from submit_diagnosis and return True
    if the submission was successful.

    Tools return a plain dict. LangGraph's ToolNode serialises it to a
    JSON string. Defensive handling for list and dict types is included
    for LangGraph version resilience.

    Returns False on any parse failure — conservative default keeps the
    session running rather than terminating incorrectly.
    """
    # Normalise list content (LangGraph structured content blocks)
    if isinstance(content, list):
        content = " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content)

    # Defensive: handle if LangGraph ever passes the dict directly
    if isinstance(content, dict):
        return content.get("data", {}).get("submitted") is True

    if not isinstance(content, str):
        return False

    # Primary path: JSON string from ToolNode serialisation
    try:
        parsed = json.loads(content)
        return parsed.get("data", {}).get("submitted") is True
    except (json.JSONDecodeError, AttributeError, TypeError):
        logger.warning(
            f"[tools_node] Could not parse submit_diagnosis response: "
            f"{str(content)[:200]}")
        return False
