# Integration tests for Condition A tools and the shared common tools.

#   pytest tests/test_condition_a_tools.py -v -m integration

from __future__ import annotations

import pytest

from tools.condition_a_tools import (
    get_service_health_a,
    get_resource_metrics,
    get_pod_events,
)


@pytest.mark.integration
class TestGetServiceHealthAIntegration:

    def test_all_services_are_up(self):
        for service in [
                "inventory-service", "order-service", "payment-service"
        ]:
            result = get_service_health_a(service)
            assert result[
                "status"] == "success", f"{service}: {result['error_message']}"
            assert result["data"]["status_summary"] == "UP"
            assert result["data"]["pod_phase"] == "Running"
            assert result["data"]["ready"] is True

    def test_response_has_required_fields(self):
        result = get_service_health_a("inventory-service")
        assert result["status"] == "success", result["error_message"]
        for field in [
                "status_summary", "pod_phase", "ready", "restart_count",
                "pod_name"
        ]:
            assert field in result["data"]

    def test_invalid_service_rejected(self):
        result = get_service_health_a("nonexistent-service")
        assert result["status"] == "error"
        assert "nonexistent-service" in result["error_message"]


@pytest.mark.integration
class TestGetResourceMetricsIntegration:

    def test_metrics_returned_and_in_valid_range(self):
        result = get_resource_metrics("inventory-service")
        assert result["status"] == "success", result["error_message"]
        assert 0.0 <= result["data"]["cpu_percent"] <= 100.0
        assert 0.0 <= result["data"]["memory_percent"] <= 100.0

    def test_response_has_required_fields(self):
        result = get_resource_metrics("inventory-service")
        assert result["status"] == "success", result["error_message"]
        for field in [
                "cpu_percent", "memory_percent", "cpu_millicores_used",
                "memory_bytes_used", "cpu_limit_millicores",
                "memory_limit_bytes", "pod_name", "note"
        ]:
            assert field in result["data"]

    def test_scrape_lag_note_present(self):
        result = get_resource_metrics("inventory-service")
        assert result["status"] == "success", result["error_message"]
        assert "15s" in result["data"]["note"]

    def test_invalid_service_rejected(self):
        result = get_resource_metrics("bogus-service")
        assert result["status"] == "error"
        assert "bogus-service" in result["error_message"]


@pytest.mark.integration
class TestGetPodEventsIntegration:

    def test_returns_success_for_running_service(self):
        result = get_pod_events("inventory-service")
        assert result["status"] == "success", result["error_message"]
        assert "event_count" in result["data"]
        assert isinstance(result["data"]["events"], list)
        assert result["data"]["event_count"] == len(result["data"]["events"])

    def test_warning_events_sort_before_normal(self):
        result = get_pod_events("inventory-service")
        assert result["status"] == "success", result["error_message"]
        events = result["data"]["events"]
        if len(events) >= 2:
            types = [e["type"] for e in events]
            warning_indices = [
                i for i, t in enumerate(types) if t == "Warning"
            ]
            normal_indices = [i for i, t in enumerate(types) if t == "Normal"]
            if warning_indices and normal_indices:
                assert max(warning_indices) < min(normal_indices)

    def test_events_belong_to_correct_service(self):
        result = get_pod_events("inventory-service")
        assert result["status"] == "success", result["error_message"]
        for event in result["data"]["events"]:
            assert event["pod_name"].startswith("inventory-service")

    def test_event_fields_present(self):
        result = get_pod_events("inventory-service")
        assert result["status"] == "success", result["error_message"]
        for event in result["data"]["events"]:
            for field in [
                    "type", "reason", "message", "count", "last_seen",
                    "pod_name"
            ]:
                assert field in event

    def test_invalid_service_rejected(self):
        result = get_pod_events("ghost-service")
        assert result["status"] == "error"
