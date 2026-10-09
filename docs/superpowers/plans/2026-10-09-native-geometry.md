# Native Geometry Patch Implementation Plan

User approved the Python/C++ split on 2026-10-09. This bounded patch adds an optional compiled 2D geometry backend to the existing engine; it preserves the existing independent monitor thread and verifies STOP during a blocked model call. It does not replace the Isaac controller or introduce a hardware safety claim.

- [x] Add tests for native geometry parity, invalid data, startup failure without the required native library, real engine completion/STOP with native geometry, and STOP during a blocked model call.
- [x] Add a small C++17 C ABI library with bounded buffers, finite-number checks, normalized coordinates, swept-disk/AABB collision checks, and no allocations/I/O in the exported functions.
- [x] Add a ctypes wrapper and server-owned `S2A_GEOMETRY_BACKEND=python|native` configuration. Native is explicit: missing library/ABI mismatch aborts startup; no automatic fallback. Keep model input unable to choose a backend or library.
- [x] Wire evaluation, execution revalidation, and monitor collision checks through the same per-engine backend. Expose the selected backend in state and run evidence.
- [x] Provide a standalone build helper and an offline benchmark including Python marshalling overhead. Do not introduce a runtime compiler or commit binary artifacts.
- [x] Build on this Windows machine, run both backend suites, test actual stop responsiveness with a blocked model call, and record benchmark sample counts and limitations.
- [x] Independent read-only `gpt-6-luna` / `max` review; resolve valid findings and re-review changes.

Existing uncommitted Isaac files and the user's design document are outside this patch. No deployment, API data egress, commit or push is part of this request.
