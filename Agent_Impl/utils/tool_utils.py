# Shared helper for building tool response dicts.
# All diagnostic tools return a plain dict via this function.
# This ensures LangGraph's ToolNode serialises the return value
# as JSON, which is required for _check_submission_succeeded in nodes.py.

from datetime import datetime, timezone


def make_tool_response(
    tool: str,
    status: str,
    data: dict = None,
    service: str = None,
    error_message: str = None,
) -> dict:
    return {
        "tool": tool,
        "status": status,
        "data": data if data is not None else {},
        "service": service,
        "timestamp_utc":
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "error_message": error_message,
    }
