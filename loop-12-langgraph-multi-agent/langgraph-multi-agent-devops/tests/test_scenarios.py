from shared_state import SCENARIOS
def test_at_least_15_scenarios():
    assert len(SCENARIOS) >= 15
def test_scenario_shape():
    required={"title","description","incident_expected","metrics","alerts","logs","version","config_changes","container_health","processes"}
    for name, scenario in SCENARIOS.items():
        assert required.issubset(scenario), name
        assert isinstance(scenario["incident_expected"], bool)
        assert "http_status" in scenario["metrics"]
