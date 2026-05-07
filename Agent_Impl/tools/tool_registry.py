# Condition boundary enforcer and system prompt builder.
#
# get_tools_and_prompt(condition) is the single entry point.
# It returns the exact tool set for the condition — no tool from the
# wrong condition is ever registered — and the condition-specific
# system prompt.

import logging
from typing import Optional
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

# Internal helpers


def _wrap(fn) -> StructuredTool:
    """
    Wrap a plain Python diagnostic tool function as a LangChain StructuredTool.
    """
    return StructuredTool.from_function(fn)


def _build_system_prompt(condition: str, tool_descriptions: str) -> str:
    """
    Build the condition-specific system prompt.

    Structure is identical for both conditions. Only the tool_descriptions
    section differs. This structural equivalence is an experimental validity
    requirement — both conditions must receive the same reasoning instructions.

    """
    return f"""You are an expert Site Reliability Engineer (SRE) diagnosing \
faults in a Spring Boot microservice testbed called the Bookstore Testbed.

## Your Task
A fault has been injected into the testbed. Investigate using your tools \
and identify the root cause. Submit your diagnosis using submit_diagnosis \
when you are confident.

## Testbed
The testbed consists of three microservices running on Kubernetes:
  - inventory-service  (manages book inventory)
  - order-service      (processes book orders, calls inventory-service)
  - payment-service    (processes payments, calls order-service)

## Available Tools
{tool_descriptions}

## Investigation Guidelines
- Start by checking the health of services to identify which is degraded.
- Follow the evidence — do not assume a fault type before investigating.
- Use multiple tools and multiple calls to build a complete picture.
- You have a maximum of 20 investigation steps before the session ends.
- A step is one tool call and its result.

"""

# Condition-specific tool description sections

_TOOL_DESCRIPTIONS_A = """\
You have the following tools. These provide generic, infrastructure-level \
observability:

  get_service_health_a(service)
    Returns pod phase, container ready status, and recent Kubernetes events
    for the specified service.

  get_resource_metrics(service)
    Returns current CPU and memory usage for the service pod as raw values
    and percentages of the configured resource limits.

  get_application_logs(service, last_n_lines, level)
    Returns recent application log lines from the service pod.
    Default level is WARN. Lower to DEBUG for more detail.

  get_pod_events(service)
    Returns Kubernetes events for the service pod — warnings, restarts,
    scheduling events, and OOMKill notifications.

  submit_diagnosis(service, component, fault_type, evidence)
    Submit your final diagnosis. This ends the session."""

_TOOL_DESCRIPTIONS_B = """\
You have the following tools. These provide framework-native, application-level \
observability via Spring Boot Actuator:

  get_service_health_b(service)
    Returns the full Spring Boot Actuator health hierarchy including all
    registered health indicator components (db, hikariPool, diskSpace, etc.)
    with their individual statuses and details.

  query_actuator_metrics(service, metric_name)
    Query Spring Boot Actuator metrics. Call without metric_name to list
    all available metrics. Call with a specific metric_name to get its
    current value. Key metrics include:
      hikaricp.connections.active / pending / max / timeout
      jvm.memory.used / jvm.memory.max
      jvm.threads.live / jvm.threads.states
      process.cpu.usage / system.cpu.usage
    Note: HikariCP pool stats appear at DEBUG level in logs — use
    this tool for pool state rather than get_application_logs.

  get_circuit_breaker_state(service)
    Returns the current Resilience4j circuit breaker state (CLOSED/OPEN/
    HALF_OPEN), failure rates, and recent event history including
    STATE_TRANSITION and ERROR events.

  get_application_logs(service, last_n_lines, level)
    Returns recent application log lines from the service pod.
    Default level is WARN. Lower to DEBUG for framework-internal detail.

  submit_diagnosis(service, component, fault_type, evidence)
    Submit your final diagnosis. This ends the session."""

# Public API


def get_tools_and_prompt(condition: str) -> tuple[list[StructuredTool], str]:
    """
    Return the tool set and system prompt for the given condition.

    This is the condition boundary enforcer. Only tools registered here
    for a condition are available to the agent. No tool from the wrong
    condition can leak through.
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
        prompt = _build_system_prompt("A", _TOOL_DESCRIPTIONS_A)

    else:  # condition == "B"
        tools = [
            _wrap(get_service_health_b),
            _wrap(query_actuator_metrics),
            _wrap(get_circuit_breaker_state),
            _wrap(get_application_logs),
            _wrap(submit_diagnosis),
        ]
        prompt = _build_system_prompt("B", _TOOL_DESCRIPTIONS_B)

    logger.info(f"Registered {len(tools)} tools for condition {condition}: "
                f"{[t.name for t in tools]}")

    return tools, prompt
