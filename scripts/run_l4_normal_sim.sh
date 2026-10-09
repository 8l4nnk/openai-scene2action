#!/usr/bin/env bash
set -eo pipefail
CODE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source /workspace/codex_jaewoo_20261009/experiment-env/env.sh
export ROS_DOMAIN_ID=110
export ROS_LOCALHOST_ONLY=1
ROOT=/workspace/s2a_normal_validation_20261009
mkdir -p "$ROOT/live" "$ROOT/logs"
/workspace/isaacsim-e02-6.1/bin/python "$CODE/prepare_l4_runtime.py"
exec flock -n /workspace/codex_jaewoo_20261009/locks/simulator.lock \
 timeout --signal=TERM --kill-after=20s 900 \
 /workspace/isaacsim-e02-6.1/bin/python -u "$CODE/normal_isaac_runtime.py" \
 --stage /workspace/k2a/ros2_moveit/attack_scene_g90/results/S05/ros2-attack-scene-knife90-clear-v9.usda \
 --controllers /workspace/scene2action_ros2_moveit/config/xarm6_isaac_controllers.yaml \
 --run-dir "$ROOT/live" --camera-hz 0.5 --camera-width 1280 --camera-height 720 \
 --observer-hz 0.5 --camera-static-burst-frames 1 --camera-static-rt-subframes 4 \
 --camera-warmup-frames 4 --duration-s 0
