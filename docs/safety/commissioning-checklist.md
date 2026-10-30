# Pre-deployment commissioning checklist

- [ ] Define part/SKU/defect taxonomy and inspection coverage with process and quality engineering.
- [ ] Confirm mounting, focus, field of view, lighting, exposure, vibration and cleaning controls.
- [ ] Record authorized camera/source inventory and network segmentation; protect camera credentials.
- [ ] Collect legally authorized examples across normal production variation, shifts and edge conditions.
- [ ] Independently label examples; resolve annotation disagreement; version train/validation/test splits.
- [ ] Measure per-defect precision/recall, false acceptance/rejection and severity-weighted misses on a blind holdout.
- [ ] Measure CPU/RAM/latency/dropped frames at actual production camera count and resolution.
- [ ] Run shadow mode without machine-control actions; operators review all events and false positives.
- [ ] Approve rollback model, monitoring, retention, audit, backups and incident process.
- [ ] Keep safety interlocks and E-stops independent; complete machine risk assessment with qualified personnel.
- [ ] Test PLC adapter first in simulation, then a non-production PLC; verify coil mapping, reset, timeouts and failure behavior.
- [ ] Obtain written approvals from plant owner, controls engineer, quality owner and safety authority before production use.

Completing this checklist does not itself certify a machine or a safety function.
