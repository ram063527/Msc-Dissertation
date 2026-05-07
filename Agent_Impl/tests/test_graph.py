# Agent_Impl/tests/test_graph.py
#
# Structural tests for the agent graph.
#
# Tests verify graph construction, condition boundary enforcement,
# and prompt integrity without making any live LLM or K8s calls.
#
# Run:
#   pytest tests/test_graph.py -v

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph.state import CompiledStateGraph
from tools.tool_registry import get_tools
from prompts.system_prompt import build_system_prompt
from agent.graph import GRAPH_RECURSION_LIMIT, build_agent
from agent.state import AgentState, build_initial_state
from config import AGENT_STEP_LIMIT

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm():
    """
    Patch ChatOpenAI so build_agent() never attempts a real LM Studio
    connection during structural tests.
    """
    with patch("agent.graph.ChatOpenAI") as mock_cls:
        mock_instance = MagicMock()
        # bind_tools() must return something callable — return the same mock
        mock_instance.bind_tools.return_value = mock_instance
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def graph_a(mock_llm):
    compiled, prompt = build_agent("A")
    return compiled, prompt


@pytest.fixture
def graph_b(mock_llm):
    compiled, prompt = build_agent("B")
    return compiled, prompt


# ---------------------------------------------------------------------------
# Expected tool sets — ground truth for boundary tests
# ---------------------------------------------------------------------------

_CONDITION_A_TOOLS = frozenset({
    "get_service_health_a",
    "get_resource_metrics",
    "get_application_logs",
    "get_pod_events",
    "submit_diagnosis",
})

_CONDITION_B_TOOLS = frozenset({
    "get_service_health_b",
    "query_actuator_metrics",
    "get_circuit_breaker_state",
    "get_application_logs",
    "submit_diagnosis",
})

# Tools exclusive to each condition — must never appear in the other
_A_EXCLUSIVE = _CONDITION_A_TOOLS - _CONDITION_B_TOOLS
_B_EXCLUSIVE = _CONDITION_B_TOOLS - _CONDITION_A_TOOLS

# ---------------------------------------------------------------------------
# 1. Build tests
# ---------------------------------------------------------------------------


class TestBuildAgent:

    def test_condition_a_returns_compiled_graph(self, graph_a):
        compiled, _ = graph_a
        assert isinstance(compiled, CompiledStateGraph)

    def test_condition_b_returns_compiled_graph(self, graph_b):
        compiled, _ = graph_b
        assert isinstance(compiled, CompiledStateGraph)

    def test_condition_a_returns_prompt_string(self, graph_a):
        _, prompt = graph_a
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_condition_b_returns_prompt_string(self, graph_b):
        _, prompt = graph_b
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_invalid_condition_raises_value_error(self, mock_llm):
        with pytest.raises(ValueError, match="Invalid condition"):
            build_agent("C")

    def test_empty_string_condition_raises_value_error(self, mock_llm):
        with pytest.raises(ValueError):
            build_agent("")

    def test_lowercase_condition_raises_value_error(self, mock_llm):
        # Conditions are case-sensitive — "a" is not "A"
        with pytest.raises(ValueError):
            build_agent("a")


# ---------------------------------------------------------------------------
# 2. Condition boundary tests
# ---------------------------------------------------------------------------


class TestConditionBoundary:
    """
    Verify that get_tools enforces strict condition boundaries.
    Tool registry is the source of truth — the compiled graph cannot
    register tools that the registry did not return.
    """

    def _get_tool_names(self, condition: str) -> frozenset[str]:
        tools = get_tools(condition)
        return frozenset(t.name for t in tools)

    def test_condition_a_has_exactly_correct_tools(self):
        actual = self._get_tool_names("A")
        assert actual == _CONDITION_A_TOOLS, (
            f"Condition A tool mismatch.\n"
            f"  Expected: {sorted(_CONDITION_A_TOOLS)}\n"
            f"  Actual:   {sorted(actual)}\n"
            f"  Missing:  {sorted(_CONDITION_A_TOOLS - actual)}\n"
            f"  Extra:    {sorted(actual - _CONDITION_A_TOOLS)}")

    def test_condition_b_has_exactly_correct_tools(self):
        actual = self._get_tool_names("B")
        assert actual == _CONDITION_B_TOOLS, (
            f"Condition B tool mismatch.\n"
            f"  Expected: {sorted(_CONDITION_B_TOOLS)}\n"
            f"  Actual:   {sorted(actual)}\n"
            f"  Missing:  {sorted(_CONDITION_B_TOOLS - actual)}\n"
            f"  Extra:    {sorted(actual - _CONDITION_B_TOOLS)}")

    def test_no_condition_b_exclusive_tool_in_condition_a(self):
        actual = self._get_tool_names("A")
        leaked = actual & _B_EXCLUSIVE
        assert not leaked, (
            f"Condition B exclusive tools found in Condition A: {leaked}")

    def test_no_condition_a_exclusive_tool_in_condition_b(self):
        actual = self._get_tool_names("B")
        leaked = actual & _A_EXCLUSIVE
        assert not leaked, (
            f"Condition A exclusive tools found in Condition B: {leaked}")

    def test_shared_tools_present_in_both_conditions(self):
        shared = _CONDITION_A_TOOLS & _CONDITION_B_TOOLS
        tools_a = self._get_tool_names("A")
        tools_b = self._get_tool_names("B")
        for tool in shared:
            assert tool in tools_a, f"Shared tool '{tool}' missing from Condition A"
            assert tool in tools_b, f"Shared tool '{tool}' missing from Condition B"

    def test_correct_tool_count_condition_a(self):
        assert len(self._get_tool_names("A")) == 5

    def test_correct_tool_count_condition_b(self):
        assert len(self._get_tool_names("B")) == 5


# ---------------------------------------------------------------------------
# 3. Prompt integrity tests
# ---------------------------------------------------------------------------


class TestPromptIntegrity:

    def test_condition_a_prompt_contains_no_b_exclusive_tools(self, graph_a):
        _, prompt = graph_a
        for tool_name in _B_EXCLUSIVE:
            assert tool_name not in prompt, (
                f"Condition B exclusive tool '{tool_name}' "
                f"found in Condition A system prompt")

    def test_condition_b_prompt_contains_no_a_exclusive_tools(self, graph_b):
        _, prompt = graph_b
        for tool_name in _A_EXCLUSIVE:
            assert tool_name not in prompt, (
                f"Condition A exclusive tool '{tool_name}' "
                f"found in Condition B system prompt")

    def test_submit_diagnosis_schema_contains_all_fault_types(self):
        """
        Fault types must be enforced via submit_diagnosis tool schema enums,
        not via the system prompt.
        """
        fault_types = {
            "connection-pool-starvation",
            "cpu-saturation",
            "circuit-breaker-open",
            "thread-pool-exhaustion",
            "memory-leak",
            "pod-oomkill",
        }
        tools = get_tools("A")
        submit = next(t for t in tools if t.name == "submit_diagnosis")
        schema = submit.args_schema.schema()
        schema_str = str(schema)
        for ft in fault_types:
            assert ft in schema_str, (
                f"Fault type '{ft}' missing from submit_diagnosis schema")

    def test_both_prompts_contain_valid_services(self, graph_a, graph_b):
        services = ["inventory-service", "order-service", "payment-service"]
        for _, prompt in [graph_a, graph_b]:
            for svc in services:
                assert svc in prompt, f"Service '{svc}' missing from prompt"


# ---------------------------------------------------------------------------
# 4. Recursion limit and state helper tests
# ---------------------------------------------------------------------------


class TestGraphConfig:

    def test_recursion_limit_formula(self):
        # GRAPH_RECURSION_LIMIT = AGENT_STEP_LIMIT * 2 + 1
        assert GRAPH_RECURSION_LIMIT == AGENT_STEP_LIMIT * 2 + 1

    def test_recursion_limit_value(self):
        # AGENT_STEP_LIMIT=20 → 41
        assert GRAPH_RECURSION_LIMIT == 41

    def test_build_initial_state_structure(self, graph_a):
        _, prompt = graph_a
        state = build_initial_state("A", prompt)
        assert state["condition"] == "A"
        assert state["step_count"] == 0
        assert state["terminated"] == False
        assert len(state["messages"]) == 2  # SystemMessage + HumanMessage
        assert state["system_prompt"] == prompt

    def test_build_initial_state_message_types(self, graph_a):
        from langchain_core.messages import HumanMessage, SystemMessage
        _, prompt = graph_a
        state = build_initial_state("A", prompt)
        assert isinstance(state["messages"][0], SystemMessage)
        assert isinstance(state["messages"][1], HumanMessage)
