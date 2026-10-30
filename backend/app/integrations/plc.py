"""PLC integration boundary. Default mode is simulation and outputs are disabled."""
from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PLCStatus:
    mode: str
    configured: bool
    connected: bool
    outputs_enabled: bool
    host: str | None
    port: int
    note: str


def _settings() -> dict[str, Any]:
    mode = os.getenv("PLC_MODE", "simulation").lower()
    host = os.getenv("PLC_HOST") or None
    try:
        port = int(os.getenv("PLC_PORT", "502"))
    except ValueError:
        port = 502
    return {
        "mode": mode,
        "host": host,
        "port": port,
        "unit_id": int(os.getenv("PLC_UNIT_ID", "1")),
        "stop_request_coil": int(os.getenv("PLC_STOP_REQUEST_COIL", "0")),
        "outputs_enabled": os.getenv("PLC_OUTPUTS_ENABLED", "false").lower() == "true",
    }


def status() -> dict[str, Any]:
    cfg = _settings()
    configured = cfg["mode"] == "simulation" or bool(cfg["host"])
    return asdict(PLCStatus(
        mode=cfg["mode"], configured=configured, connected=False,
        outputs_enabled=cfg["outputs_enabled"], host=cfg["host"], port=cfg["port"],
        note="Simulation mode; no hardware is contacted." if cfg["mode"] == "simulation" else "Connection state is checked on demand.",
    ))


def _client():
    cfg = _settings()
    if cfg["mode"] != "modbus_tcp":
        raise RuntimeError("PLC_MODE must be modbus_tcp to access a Modbus TCP device")
    if not cfg["host"]:
        raise RuntimeError("PLC_HOST is not configured")
    try:
        from pymodbus.client import ModbusTcpClient
    except ImportError as exc:
        raise RuntimeError("Install lineguard-cv[plc] to enable Modbus TCP") from exc
    return cfg, ModbusTcpClient(cfg["host"], port=cfg["port"], timeout=2)


def test_connection() -> dict[str, Any]:
    cfg = _settings()
    if cfg["mode"] == "simulation":
        return {"connected": True, "mode": "simulation", "message": "PLC adapter simulation responded; no physical PLC was contacted."}
    client = None
    try:
        _, client = _client()
        connected = bool(client.connect())
        return {"connected": connected, "mode": cfg["mode"], "message": "Modbus TCP connection successful (read/write outputs were not touched)." if connected else "Could not connect to the PLC."}
    except Exception as exc:
        return {"connected": False, "mode": cfg["mode"], "message": str(exc)[:300]}
    finally:
        if client:
            client.close()


def request_machine_stop(*, confirmation: str, safety_acknowledged: bool) -> dict[str, Any]:
    """Issue an explicitly requested *PLC stop-request bit*, never a safety relay command."""
    cfg = _settings()
    if confirmation != "REQUEST_STOP" or safety_acknowledged is not True:
        raise ValueError("Explicit REQUEST_STOP confirmation and safety acknowledgement are required")
    if cfg["mode"] == "simulation":
        return {"accepted": True, "simulated": True, "message": "Simulated stop request recorded; no machine or PLC was contacted."}
    if not cfg["outputs_enabled"]:
        raise PermissionError("PLC outputs are disabled. Set PLC_OUTPUTS_ENABLED=true only after commissioning the dedicated request bit.")
    client = None
    write_attempted = False
    try:
        _, client = _client()
        if not client.connect():
            raise ConnectionError("PLC connection failed")
        write_attempted = True
        try:
            coil = client.write_coil(cfg["stop_request_coil"], True, device_id=cfg["unit_id"])
        except TypeError:
            coil = client.write_coil(cfg["stop_request_coil"], True, slave=cfg["unit_id"])
        if coil.isError():
            raise RuntimeError("PLC rejected the stop-request write")
        time.sleep(0.25)
        return {"accepted": True, "simulated": False, "message": "Momentary stop-request bit sent. Independently confirm machine state; software acknowledgement does not prove a stop."}
    finally:
        if client and write_attempted:
            try:
                try:
                    reset = client.write_coil(cfg["stop_request_coil"], False, device_id=cfg["unit_id"])
                except TypeError:
                    reset = client.write_coil(cfg["stop_request_coil"], False, slave=cfg["unit_id"])
                if reset.isError():
                    raise RuntimeError("PLC did not acknowledge reset of the momentary request bit")
            finally:
                client.close()
        elif client:
            client.close()
