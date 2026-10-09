# C++ Geometry Integration Plan

> Execute inline with test-driven verification and the repository's independent Luna/max review.

Goal: Keep the Python web/model/evaluation layer and add an explicitly configured C++ F3 kernel. Preserve independent monitor and STOP behavior during slow model evaluation. This patch remains a normalized 2D simulator; it does not add a physical controller or claim Isaac task completion.

Design: A small C ABI library checks a complete point path against expanded AABBs. `ctypes.CDLL` invokes the kernel without holding the Python GIL. Engine construction selects `python` (default) or `cpp` via server environment. A missing/incompatible configured C++ library prevents startup; there is no automatic backend switch. Evaluation, execution revalidation and every movement tick use the same selected checker.

The implementation was consolidated with concurrent work into `scripts/build_native.py`, `NativeGeometry` and `S2A_GEOMETRY_BACKEND=python|native`. The current checklist is maintained in [2026-10-09-native-geometry.md](2026-10-09-native-geometry.md); measured results are in [geometry-validation-2026-10-09.md](../../geometry-validation-2026-10-09.md). The initial `cpp` setting/library names below are superseded by `native` and `S2A_NATIVE_LIBRARY`.

Files: `native/geometry.cpp`, `scripts/build_native.py`, `scene2action/geometry.py`, `scene2action/engine.py`, `tests/test_geometry.py`, `tests/test_api.py`, documentation and benchmark script.

- [x] Add failing tests for C++ selection, invalid/boundary inputs, Python/C++ parity and end-to-end engine execution/STOP.
- [x] Build the local shared library with the installed compiler, strict floating-point semantics and no fast-math.
- [x] Implement the checker interface and route every Engine F3 check through it, recording backend identity.
- [x] Test STOP responsiveness and monitor progress while a synthetic slow model request is pending; no external model calls.
- [x] Run full regression tests, real compiled-kernel parity tests and a bounded geometry benchmark. Report measured overhead as well as speedup.
- [x] Obtain independent read-only `gpt-6-luna` / `max` review, fix valid findings and re-review.
- [x] Activate the reviewed C++ backend in the local workbench and verify state without making model calls or running robot commands.

Constraints: Preserve all pre-existing uncommitted work, especially `isaac/` and the user's design document. No changes to remote Pods, credentials, hazardous action generation or external corpus transmission in this patch. The monitor remains a Python thread in this version; separate native controller process and physical STOP require a later adapter and verification.
