#!/bin/bash
set -eu
cd /tmp/s2a-normal-code || exit 1
/isaac-sim/python.sh baseline_launcher.py
/isaac-sim/python.sh - <<'PY'
from pathlib import Path
from evidence_viewer import evidence_state
import json
print('S2A_BASELINE_EVIDENCE',json.dumps(evidence_state(Path('/tmp/s2a-normal-evidence'))),flush=True)
PY
/isaac-sim/python.sh evidence_viewer.py &
sleep infinity
