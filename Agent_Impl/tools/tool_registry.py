# Condition boundary enforcer.
# get_tools(condition) is the single entry point.
# Returns the exact tool set for the condition.
# No tool from the wrong condition is ever registered.

import logging
from langchain_core.tools import StructuredTool
from config import VALID_CONDITIONS
from tools.common_tools import get_application_logs, submit_diagnosis
from tools.condition_a_tools import (
    get_pod_events,
    get_resource_metrics,
    get_service_health_a,
)
from tools.condition_b_tools import (
    get_circuit_breaker_state,
    get_service_health_b,
    query_actuator_metrics,
)

logger = logging.getLogger(__name__)


def _wrap(fn) -> StructuredTool:
    return StructuredTool.from_function(fn)


def get_tools(condition: str) -> list[StructuredTool]:
    """
    Return the tool set for the given condition.
    This is the condition boundary enforcer — only tools registered
    here are available to the agent for this condition.
    """
    if condition not in VALID_CONDITIONS:
        raise ValueError(f"Invalid condition '{condition}'. "
                         f"Must be one of: {sorted(VALID_CONDITIONS)}")

    if condition == "A":
        tools = [
            _wrap(get_service_health_a),
            _wrap(get_resource_metrics),
            _wrap(get_application_logs),
            _wrap(get_pod_events),
            _wrap(submit_diagnosis),
        ]
    else:  # condition == "B"
        tools = [
            _wrap(get_service_health_b),
            _wrap(query_actuator_metrics),
            _wrap(get_circuit_breaker_state),
            _wrap(get_application_logs),
            _wrap(submit_diagnosis),
        ]

    logger.info(f"Registered {len(tools)} tools for condition {condition}: "
                f"{[t.name for t in tools]}")
    return tools
