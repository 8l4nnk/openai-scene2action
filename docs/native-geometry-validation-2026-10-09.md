# Native geometry patch verification

Scope: optional C++17 normalized 2D swept-disk/AABB kernel, Python ctypes bridge, fixed per-engine backend selection, evaluation/execution/monitor integration. Model calls stay in Python. The existing simulator monitor remains a separate Python thread; no native controller, independent process watchdog, Isaac 3D validation, or hardware stop is claimed.

Windows installed LLVM clang++ built `.data/native/s2a_geometry.dll` successfully with -std=c++17 -O2 -Wall -Wextra -Werror -shared, without fast-math. No dependency or compiler was installed. No binary was committed. Default backend remains Python; native is explicit and missing/ABI-incompatible binaries stop startup without fallback.

Tests: native mandatory related engine/API suite 63 passed; final full suite with S2A_REQUIRE_NATIVE_TESTS=1 and S2A_GEOMETRY_BACKEND=native: 94 passed, 1 skipped, 1 upstream Starlette TestClient deprecation warning. The skipped test relates to Windows symlink permissions, not native coverage. Earlier full run exposed 2 in-progress Isaac evidence tests outside this patch; they were passing in the final suite. They were not edited by this patch.

Coverage: 500 seeded paths comparing backends; crossing, contact, clearance, bounds, NaN/infinity/negative radius/malformed boxes, raw C ABI null pointers and oversized counts, missing required native binary, native run evidence/STOP/reuse rejection. API test holds a planner callback, starts a previously prepared run, observes monitor movement while the callback is blocked, sends STOP, and verifies late candidate HOLD with no stale execution. This proves local simulated concurrency behavior, not a real-time deadline.

A regression test found the Python slab test ignored a tiny segment whose endpoint crossed an expanded obstacle boundary. Both endpoint bounds are now considered in the near-zero-delta branch. The test failed on Python before the fix and passed after the fix.

Benchmark: each fixture 200 samples after 10 warmups, p50 below, includes validation and ctypes marshalling. Measurements ran alongside local tests and may include host scheduling/load. Repeated clear-path obstacles are synthetic compute fixtures, not factory scenes or end-to-end timings.

| Commands / obstacles | Python p50 us | Native p50 us | Ratio |
|---|---:|---:|---:|
| 8 / 0 | 25.6 | 14.0 | 1.829 |
| 16 / 128 | 3241.9 | 387.2 | 8.373 |
| 64 / 512 | 74512.3 | 1728.9 | 43.098 |

Independent read-only reviewer: `/root/review_native_geometry`, explicitly created with model `gpt-6-luna`, reasoning_effort `max`, fork_turns `none`. Reviewed C ABI, ctypes/loader, Engine evaluate/execute/tick, simulator near-zero boundary, build/benchmark code, and tests. Final P0-P3 findings: none. Reviewer did not independently execute tests.

No external API calls, Pod changes, commit/push, or running-server restart were performed by this performance patch. Enable the backend with the commands in native/README.md after rebuilding on the target platform.
