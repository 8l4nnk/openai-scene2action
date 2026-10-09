#!/bin/bash
set -eu
cd /workspace/scene2action_migrated_20261009/runtime
/isaac-sim/python.sh migration.py
/isaac-sim/python.sh -c 'from migration import ROOT, atomic_json; atomic_json(ROOT / "public/state.json", {"state":"STARTING", "frame":False, "normal_motion_verified":False, "filter_integration":False})'
/isaac-sim/python.sh migration_viewer.py &
VIEWER_PID=$!
trap 'kill "$VIEWER_PID" 2>/dev/null || true' EXIT
set +e
timeout 600 /isaac-sim/python.sh migration_render.py
RENDER_EXIT=$?
set -e
if [ "$RENDER_EXIT" -ne 0 ]; then
  /isaac-sim/python.sh -c 'from migration import ROOT, atomic_json; atomic_json(ROOT / "public/state.json", {"state":"MIGRATION_FAILED", "frame":False, "normal_motion_verified":False, "filter_integration":False})'
fi
wait "$VIEWER_PID"
