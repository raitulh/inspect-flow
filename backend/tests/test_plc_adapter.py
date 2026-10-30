import pytest

from app.integrations.plc import request_machine_stop, status, test_connection as plc_test_connection


def test_plc_defaults_to_simulation(monkeypatch):
    monkeypatch.delenv("PLC_MODE", raising=False)
    monkeypatch.delenv("PLC_OUTPUTS_ENABLED", raising=False)
    state = status()
    assert state["mode"] == "simulation"
    assert state["outputs_enabled"] is False
    assert plc_test_connection()["connected"] is True


def test_stop_request_requires_explicit_confirmation(monkeypatch):
    monkeypatch.setenv("PLC_MODE", "simulation")
    with pytest.raises(ValueError):
        request_machine_stop(confirmation="", safety_acknowledged=False)


def test_simulated_stop_request_never_contacts_hardware(monkeypatch):
    monkeypatch.setenv("PLC_MODE", "simulation")
    result = request_machine_stop(confirmation="REQUEST_STOP", safety_acknowledged=True)
    assert result["accepted"] is True
    assert result["simulated"] is True
