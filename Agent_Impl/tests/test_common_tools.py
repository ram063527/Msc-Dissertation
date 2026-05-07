# Run:
#   pytest tests/test_common_tools.py -v -m integration

from __future__ import annotations
import pytest

from tools.common_tools import get_application_logs, submit_diagnosis


# PATTERN: result.status      → result["status"]
# PATTERN: result.data        → result["data"]
# PATTERN: result.error_message → result["error_message"]


@pytest.mark.integration
class TestGetApplicationLogsIntegration:

    def test_returns_success_for_all_services(self):
        for service in [
                "inventory-service", "order-service", "payment-service"
        ]:
            result = get_application_logs(service)
            assert result["status"] == "success", (
                f"{service}: {result['error_message']}")

    def test_response_has_required_fields(self):
        result = get_application_logs("inventory-service")
        assert result["status"] == "success", result["error_message"]
        for field in [
                "level_filter", "pod_name", "pod_restarted", "restart_count",
                "current_logs", "current_truncated", "previous_logs"
        ]:
            assert field in result["data"], f"Missing field: {field}"

    def test_default_level_filter_is_warn(self):
        result = get_application_logs("inventory-service")
        assert result["status"] == "success", result["error_message"]
        assert result["data"]["level_filter"] == "WARN"

    def test_debug_filter_returns_more_lines_than_warn(self):
        warn = get_application_logs("inventory-service", level="WARN")
        debug = get_application_logs("inventory-service", level="DEBUG")
        assert warn["status"] == "success", warn["error_message"]
        assert debug["status"] == "success", debug["error_message"]
        # DEBUG includes everything WARN includes plus more
        assert len(debug["data"]["current_logs"]) >= len(
            warn["data"]["current_logs"])

    def test_error_filter_returns_subset_of_warn(self):
        warn = get_application_logs("inventory-service", level="WARN")
        error = get_application_logs("inventory-service", level="ERROR")
        assert warn["status"] == "success", warn["error_message"]
        assert error["status"] == "success", error["error_message"]
        assert len(error["data"]["current_logs"]) <= len(
            warn["data"]["current_logs"])

    def test_current_logs_is_list(self):
        result = get_application_logs("inventory-service")
        assert result["status"] == "success", result["error_message"]
        assert isinstance(result["data"]["current_logs"], list)

    def test_no_previous_logs_when_no_restart(self):
        result = get_application_logs("inventory-service")
        assert result["status"] == "success", result["error_message"]
        # Under normal conditions pods have not restarted
        if not result["data"]["pod_restarted"]:
            assert result["data"]["previous_logs"] is None

    def test_last_n_lines_respected(self):
        result = get_application_logs("inventory-service",
                                      last_n_lines=10,
                                      level="DEBUG")
        assert result["status"] == "success", result["error_message"]
        assert len(result["data"]["current_logs"]) <= 10

    def test_invalid_level_falls_back_gracefully(self):
        result = get_application_logs("inventory-service", level="VERBOSE")
        assert result["status"] == "success", result["error_message"]
        # Should fall back to DEFAULT_LOG_LEVEL, not crash
        assert result["data"]["level_filter"] in ["WARN", "ERROR", "INFO"]

    def test_invalid_service_rejected(self):
        result = get_application_logs("fake-service")
        assert result["status"] == "error"
        assert "fake-service" in result["error_message"]
