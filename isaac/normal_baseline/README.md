# Isolated Isaac normal baseline

This is a normal-only S05 adaptation of the user's supplied `four_environment_workcell.py`, evaluator, xArm kinematics and configuration artifacts. It rebuilds the xArm scene using the existing S05 normal-work configuration; it does **not** load the saved scene containing the person and tools.

It is an oracle controller baseline, **not yet the workbench filter-to-Isaac integration**. No VLM, ROS2 or hardware endpoint is called. Normal work is limited to red ball → zone 1 followed by blue ball → zone 2. Only initialization sets object poses; execution commands the articulation and observes dynamic objects. A failed contact, lift, transfer or placement check ends the run as failed. `/tmp/s2a-normal-evidence/STOP` pauses the world before the next articulation command; this local mechanism has not yet been tested on the GPU.

Run inside the official Isaac 6.1 container:

```sh
/isaac-sim/python.sh normal_workcell.py --scenario S05 --run-id normal-20261009-01 --output-root /tmp/s2a-normal-evidence
```

Each run records source hashes, joint commands, observed object poses, contacts, per-object checks, snapshots and an MP4. The copied sphere damping values were tuned in the earlier simulator and are not material calibration for a real robot. Successful execution is not a claim of human safety, SA02–SA17 coverage, or F2/F3 integration.

The baseline is run only after independent review. A created Pod or a passing local contract test is not evidence of a successful physical simulation.
