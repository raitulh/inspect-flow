# PLC integration and machine-stop request boundary

LineGuard includes an optional Modbus TCP integration adapter. The default is `PLC_MODE=simulation`; this makes no hardware connection. The adapter can test a Modbus TCP connection without writing outputs. Physical output writes are disabled by default (`PLC_OUTPUTS_ENABLED=false`).

## Environment settings

```dotenv
PLC_MODE=simulation
PLC_HOST=
PLC_PORT=502
PLC_UNIT_ID=1
PLC_STOP_REQUEST_COIL=0
PLC_OUTPUTS_ENABLED=false
```

For a lab PLC simulator, install `pip install -e '.[plc]'`, set `PLC_MODE=modbus_tcp`, and configure the host/unit/coil according to the simulator vendor. Test connection first. A manual stop-request endpoint requires the literal confirmation `REQUEST_STOP` and `safety_acknowledged=true`; API access is role-restricted and every accepted request is audited. In simulation it records only a simulated request.

To send a real momentary write, an authorized controls engineer must commission a dedicated, isolated **request bit** and explicitly enable `PLC_OUTPUTS_ENABLED=true`. The adapter asserts and then resets the configured coil. Commissioning must confirm addressing, pulse timing, network loss behavior, PLC program semantics, duplicate/replay behavior and actual machine response. A failed reset requires independent operator verification.

## Safety boundary

- The AI pipeline never automatically stops a machine when it detects a defect.
- This is not a safety PLC, emergency stop, guard interlock, safety relay, SIL/PL-rated function or certified protective device.
- Never map this request coil directly to a motor contactor, actuator output or emergency-stop loop.
- The machine's existing hardwired emergency stops, guards, interlocks and certified safety logic must remain independent and take precedence.
- A stop request is not proof that a machine has stopped. Verify actual state using independent PLC telemetry and the plant's approved procedure.
- Begin with simulation. Obtain site controls/safety approval, complete hazard and risk assessment, commission on a non-production test rig, add access/network safeguards, and validate failure modes before any plant deployment.

LineGuard does not claim factory safety certification. Certification, regulatory conformity and machine risk acceptance require qualified professionals, applicable standards, the actual machine and independent assessment.
