# Run:
#   pytest tests/test_condition_b_tools.py -v -m integration

import pytest

from tools.condition_b_tools import (
    get_service_health_b,
    query_actuator_metrics,
    get_circuit_breaker_state,
)


@pytest.mark.integration
class TestGetServiceHealthBIntegration:

    def test_all_services_return_up(self):
        for service in [
                "inventory-service", "order-service", "payment-service"
        ]:
            result = get_service_health_b(service)
            assert result["status"] == "success", f"{service}: {result['error_message']}"
            assert result["data"]["status"] == "UP", (
                f"{service} actuator health is not UP: {result['data']}")

    def test_response_contains_components(self):
        result = get_service_health_b("inventory-service")
        assert result["status"] == "success", result["error_message"]
        assert "components" in result["data"]
        assert isinstance(result["data"]["components"], dict)
        assert len(result["data"]["components"]) > 0

    def test_db_component_present_and_up(self):
        # All services connect to Postgres — db component must be UP
        for service in ["inventory-service", "order-service"]:
            result = get_service_health_b(service)
            assert result["status"] == "success", f"{service}: {result['error_message']}"
            components = result["data"].get("components", {})
            assert "db" in components, f"'db' component missing for {service}"
            assert components["db"]["status"] == "UP", (
                f"db DOWN for {service}: {components['db']}")

    def test_payment_service_has_no_direct_db_connection(self):
        # payment-service does not hold a direct DB connection
        result = get_service_health_b("payment-service")
        assert result["status"] == "success", f"{service}: {result['error_message']}"
        components = result["data"].get("components", {})
        assert "db" not in components

    def test_invalid_service_rejected(self):
        result = get_service_health_b("ghost-service")
        assert result["status"] == "error"
        assert "ghost-service" in result["error_message"]


@pytest.mark.integration
class TestQueryActuatorMetricsIntegration:

    def test_metric_list_returned_when_no_name_given(self):
        result = query_actuator_metrics("inventory-service")
        assert result["status"] == "success", result["error_message"]
        assert "available_metrics" in result["data"]
        assert isinstance(result["data"]["available_metrics"], list)
        assert result["data"]["count"] > 0

    def test_metric_list_contains_expected_names(self):
        result = query_actuator_metrics("inventory-service")
        assert result["status"] == "success", result["error_message"]
        names = result["data"]["available_metrics"]
        for expected in [
                "jvm.memory.used",
                "jvm.threads.live",
                "process.cpu.usage",
                "http.server.requests",
        ]:
            assert expected in names, f"Expected metric '{expected}' not found"

    def test_jvm_memory_used_returns_measurement(self):
        result = query_actuator_metrics("inventory-service", "jvm.memory.used")
        assert result["status"] == "success", result["error_message"]
        assert result["data"]["metric_name"] == "jvm.memory.used"
        measurements = result["data"]["measurements"]
        assert len(measurements) > 0
        # VALUE statistic must be present and positive
        values = [
            m["value"] for m in measurements if m["statistic"] == "VALUE"
        ]
        assert len(values) > 0
        assert values[0] > 0

    def test_hikaricp_active_connections_returned(self):
        result = query_actuator_metrics("inventory-service",
                                        "hikaricp.connections.active")
        assert result["status"] == "success", result["error_message"]
        assert result["data"]["metric_name"] == "hikaricp.connections.active"
        assert len(result["data"]["measurements"]) > 0

    def test_process_cpu_usage_in_valid_range(self):
        result = query_actuator_metrics("inventory-service",
                                        "process.cpu.usage")
        assert result["status"] == "success", result["error_message"]
        measurements = result["data"]["measurements"]
        values = [
            m["value"] for m in measurements if m["statistic"] == "VALUE"
        ]
        assert len(values) > 0
        assert 0.0 <= values[0] <= 1.0

    def test_jvm_threads_live_is_positive_integer(self):
        result = query_actuator_metrics("inventory-service",
                                        "jvm.threads.live")
        assert result["status"] == "success", result["error_message"]
        values = [
            m["value"] for m in result["data"]["measurements"]
            if m["statistic"] == "VALUE"
        ]
        assert values[0] > 0

    def test_invalid_metric_name_returns_error(self):
        result = query_actuator_metrics("inventory-service", "made.up.metric")
        assert result["status"] == "error"

    def test_invalid_service_rejected(self):
        result = query_actuator_metrics("ghost-service", "jvm.memory.used")
        assert result["status"] == "error"
        assert "ghost-service" in result["error_message"]

    def test_note_present_in_list_response(self):
        result = query_actuator_metrics("inventory-service")
        assert result["status"] == "success", result["error_message"]
        assert "note" in result["data"]


@pytest.mark.integration
class TestGetCircuitBreakerStateIntegration:

    def test_circuit_breakers_present_for_order_service(self):
        # order-service has Resilience4j configured
        result = get_circuit_breaker_state("order-service")
        assert result["status"] == "success", result["error_message"]
        assert "circuit_breakers" in result["data"]
        assert len(result["data"]["circuit_breakers"]) > 0

    def test_all_circuit_breakers_closed_under_normal_conditions(self):
        for service in ["order-service", "payment-service"]:
            result = get_circuit_breaker_state(service)
            assert result["status"] == "success", f"{service}: {result['error_message']}"
            for cb_name, cb_state in result["data"]["circuit_breakers"].items():
                assert cb_state["state"] == "CLOSED", (
                    f"Circuit breaker '{cb_name}' on {service} "
                    f"expected CLOSED, got {cb_state['state']}")

    def test_response_has_required_fields(self):
        result = get_circuit_breaker_state("order-service")
        assert result["status"] == "success", result["error_message"]
        for field in [
                "circuit_breakers", "event_count_total", "events_shown",
                "events", "events_note"
        ]:
            assert field in result["data"], f"Missing field: {field}"

    def test_events_list_is_present(self):
        result = get_circuit_breaker_state("order-service")
        assert result["status"] == "success", result["error_message"]
        assert isinstance(result["data"]["events"], list)

    def test_events_capped_at_max(self):
        result = get_circuit_breaker_state("order-service")
        assert result["status"] == "success", result["error_message"]
        assert result["data"]["events_shown"] <= 20

    def test_success_events_capped_at_five(self):
        result = get_circuit_breaker_state("order-service")
        assert result["status"] == "success", result["error_message"]
        success_events = [
            e for e in result["data"]["events"] if e.get("type") == "SUCCESS"
        ]
        assert len(success_events) <= 5

    def test_event_fields_present(self):
        result = get_circuit_breaker_state("order-service")
        assert result["status"] == "success", result["error_message"]
        for event in result["data"]["events"]:
            assert "type" in event
            assert "circuitBreakerName" in event
            assert "creationTime" in event

    def test_invalid_service_rejected(self):
        result = get_circuit_breaker_state("ghost-service")
        assert result["status"] == "error"
