# Local Simulator MVP Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for inline implementation and the repository's mandatory Luna max review. Track steps with checkboxes.

**Goal:** Run two normal-work contracts through F1, F2, Adapter revalidation and F3 in a local browser application, with simulation, trace history and measured latency.

**Architecture:** A local FastAPI service owns trusted contracts, simulator state and execution authority. A replaceable planner proposes actions; the engine validates and binds approvals to immutable snapshots. A separate simulator tick performs bounded execution and records terminal outcomes in SQLite.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic, Pillow, SQLite, vanilla HTML/CSS/JS, pytest; optional OpenAI Responses planner. Dependencies are locked with uv.

**Spec:** `오늘 설계안.md` (user-approved design; local simulator selected explicitly).

## Global constraints

- Codex only for development; independent reviewer: gpt-6-luna / max / fork_turns=none.
- Preserve the user's existing edit to 오늘 설계안.md. Work on codex/local-simulator-mvp.
- SYSTEM PROMPT defines normal work. TEXT, IMAGE with no user text, IMAGE+TEXT are input conditions.
- Simulator images are generated from server-owned state; no arbitrary upload is treated as a current physical observation.
- Built-in replay planner is explicitly labeled synthetic; OpenAI planner requires configured key/model and opt-in. No silent fallback from live to replay.
- Scope: 2D point-carrier with circular clearance and axis-aligned obstacles. No articulated-arm/3D/force/human-safety claim. No physical robot adapter or AWS deployment.
- Policies are trusted server configuration. First local implementation uses a replaceable Python policy evaluator; OPA, ROS2, MoveIt, MCAP and cloud are later adapters, not claimed integrated.
- BLOCK/HOLD/errors deliver zero commands. STOP clears remaining commands. New evaluation and explicit execution are required after stop.
- No performance SLA before measurement; per-stage timings and sample count are exposed, without implying field accuracy.

## Review focus

1. Plan/observation/contract changes after evaluation must invalidate execution.
2. Duplicate execution, concurrent preparation, stop and retries must not duplicate movement.
3. Stale sensors, planner errors, empty/malformed output and nonfinite values must not approve execution.
4. Full 2D segments and carried-object clearance, not only endpoints, must be checked.
5. API origin/host validation, bounded text/body sizes and persistence failure must not expose execution to cross-origin calls or produce unrecorded approvals.

## Files and interfaces

- `scene2action/models.py`: strict request, plan, contract, world and trace schemas.
- `scene2action/contracts.py`, `contracts/*.json`: load two reviewed normal-work definitions and simulator fixtures.
- `scene2action/planners.py`: `ReplayPlanner.propose(request, contract, snapshot)` and optional `OpenAIPlanner.propose(...)` produce a candidate plus source metadata; no execution capability.
- `scene2action/simulator.py`: immutable snapshots, command expansion, segment collision and bounded movement.
- `scene2action/engine.py`: `evaluate(request)`, `execute(run_id)`, `tick()`, `stop()`, `reset(contract_id)`, simulator disturbance controls.
- `scene2action/store.py`: durable run/evidence/transition records; no credentials.
- `scene2action/app.py`: local-only HTTP API, lifecycle ticker and static UI.
- `scene2action/static/*`: Korean operator UI with scene, pipeline, timeline, metrics and input modes.
- `tests/*`: real engine, simulator, temporary SQLite and API tests.

## Task 1: Contracts, candidate validation and F1/F2

- [x] Write failing tests: normal sort/kit accepted; wrong destination/order/ID rejected; IMAGE rejects user text; missing TEXT held; planner exceptions/malformed output held; finite numbers enforced.
- [x] Run `uv run pytest tests/test_engine.py -q`, observe failures for missing behavior.
- [x] Implement models, trusted contracts, replay provider and evaluation interfaces.
- [x] Optional Responses adapter consumes image only for IMAGE mode, sets normal work in instructions and returns parsed schema. Missing configuration is HOLD. Tests inject an offline provider; no paid API calls during verification.
- [x] Run the task tests and inspect results.

## Task 2: Adapter/F3 and execution lifecycle

- [x] Write failing tests: mismatched Adapter sequence blocked, mid-segment obstacle blocked, stale approval held, state revision change stops, duplicate start does not replay, stop clears commands, fresh normal run completes both contracts.
- [x] Implement approach/grasp/transfer/release command expansion with object/target/position binding and 2D collision clearance.
- [x] Implement single-active-run lock, monotonic approval deadlines, sensor freshness checks, bounded steps and durable transitions.
- [x] Run `uv run pytest tests/test_engine.py tests/test_simulator.py -q` and inspect results.

## Task 3: Local API, persistence and operator screen

- [x] Write failing API tests: evaluate/start/stop/history round trip, restart invalidates unfinished approvals, bad origin/host denied, unknown fields/oversized bodies rejected, live config absence held.
- [x] Add local lifecycle ticker, SQLite repository and loopback server entry point.
- [x] Build responsive scene SVG and pipeline/timeline UI. All external strings render with textContent. Buttons show pending/errors and require explicit start after evaluation.
- [x] Provide TEXT/IMAGE/IMAGE+TEXT, two contracts, replay scenarios, optional live planner, obstacle/sensor loss/stop controls, run history and JSON evidence export.
- [x] Run `uv run pytest -q`; run actual HTTP smoke checks and browser interaction at desktop and narrow widths.

## Task 4: Reproducibility and review

- [x] Add README, .env.example without secrets, dependency lock and benchmark CLI. Distinguish simulation/planner timings and sample-based metrics from safety performance.
- [x] Run `uv run pytest -q`, JS syntax check, benchmark and git diff whitespace check.
- [x] Request read-only gpt-6-luna/max independent review of all new files and README, compared with 3bf4a06; include tests and scope limitations.
- [x] Fix valid findings, rerun relevant/full tests and request re-review of changed paths. Report reviewer settings and remaining limits.

## Progress

- Plan created after the user requested implementation and explicitly selected local simulation. Implementation is authorized in this chat; no cloud or real robot execution is included.
- Baseline: repository contains guidance/design/README/LICENSE only; no executable baseline test suite exists.
