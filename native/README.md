# Optional C++ geometry backend

This C++17 library accelerates the existing normalized **2D** swept-disk/AABB checks. It does not implement Isaac 3D collisions, robot control, or a hardware emergency stop. Model calls remain in Python; the simulator monitor remains its existing separate Python thread.

Build with an installed clang++/g++ compatible compiler:

```powershell
.venv/Scripts/python.exe scripts/build_native.py
# Optional: --compiler 'C:/Program Files/LLVM/bin/clang++.exe'
```

The binary is written under Git-excluded `.data/native/`. No compiler is installed automatically and no build occurs at startup. Linux requires rebuilding on Linux; Windows DLLs cannot be copied to a Linux Pod.

Select the backend explicitly before starting the app:

```powershell
$env:S2A_GEOMETRY_BACKEND='native'
# Optional operator-owned absolute library path:
# $env:S2A_NATIVE_LIBRARY='C:/path/to/s2a_geometry.dll'
uv run --env-file .env python -m scene2action
```

Default `S2A_GEOMETRY_BACKEND=python` preserves a compiler-free installation. When native is requested, a missing/incompatible library aborts startup; there is no silent fallback. Never load a library supplied by model/user input. State and per-run evidence expose the selected backend. The same backend checks evaluation, execution revalidation, and monitor movement.

```powershell
$env:S2A_REQUIRE_NATIVE_TESTS='1'
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m scene2action.geometry_benchmark --samples 200
```

Native tests may skip when the optional library is not built. Setting `S2A_REQUIRE_NATIVE_TESTS=1` makes missing-library checks fail instead, preventing a misleading native verification report.

The benchmark includes Python validation and ctypes marshalling. Its obstacle fixtures deliberately repeat clear-path boxes to measure computation, and do not represent a factory scene. A faster dense fixture does not establish faster model responses, an end-to-end SLA, or a real-time stopping guarantee.
