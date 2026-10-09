"""Load and render the migrated original USD, with its timeline stopped."""
import json
import time
import traceback
from pathlib import Path

from migration import ROOT, REQUIRED, atomic_json, digest, copy_verified

PUBLIC = ROOT / 'public'
PUBLIC.mkdir(parents=True, exist_ok=True)
state = {'state': 'STARTING', 'stage_preserved': False, 'normal_motion_verified': False,
         'filter_integration': False, 'frame': False, 'started_at': time.time()}
atomic_json(PUBLIC / 'state.json', state)
app = None
try:
    from isaacsim import SimulationApp
    app = SimulationApp({'headless': True, 'renderer': 'RayTracedLighting',
                         'multi_gpu': False, 'anti_aliasing': 2})
    import cv2
    import numpy as np
    import omni.usd
    import omni.timeline
    import omni.replicator.core as rep
    from pxr import Usd, UsdGeom, Sdf, UsdUtils, Ar

    path = ROOT / 'original/scene/environment.usdc'
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    expected = manifest['original_stage_sha256']
    assert digest(path) == expected, 'Migrated stage changed'
    # Compose the saved USD and localize its asset paths in a runtime copy.
    # Isaac's built-in MDL modules remain runtime dependencies, as they are
    # compiler module names rather than ordinary files that USDZ can package.
    layers, assets, unresolved = UsdUtils.ComputeAllDependencies(str(path))
    assert not unresolved, 'Unresolved USD dependencies: ' + str(unresolved)
    original_stage = Usd.Stage.Open(str(path))
    assert original_stage, 'Cannot open saved USD'
    flat = original_stage.Flatten()
    runtime_materials = {}
    localized_assets = {}
    builtin_names = {'OmniPBR.mdl', 'OmniGlass.mdl', 'OmniSurfaceBase.mdl'}

    def localize(asset_path):
        if not asset_path:
            return asset_path
        if asset_path in builtin_names:
            candidates = list(Path('/isaac-sim').rglob(asset_path))
            assert candidates, 'Missing Isaac built-in material: ' + asset_path
            runtime_materials[asset_path] = str(candidates[0])
            return asset_path
        resolved = Path(str(Ar.GetResolver().Resolve(asset_path)))
        assert resolved.is_file(), 'Cannot localize asset: ' + asset_path
        name = digest(resolved) + resolved.suffix
        destination = ROOT / 'runtime/assets' / name
        localized_assets[str(destination)] = copy_verified(resolved, destination)
        return str(destination)

    UsdUtils.ModifyAssetPaths(flat, localize)
    runtime_stage_path = ROOT / 'runtime/environment.usdc'
    assert flat.Export(str(runtime_stage_path))
    runtime_layers, runtime_assets, runtime_unresolved = UsdUtils.ComputeAllDependencies(str(runtime_stage_path))
    assert not runtime_unresolved, 'Unresolved localized dependencies: ' + str(runtime_unresolved)
    external = [str(x.realPath or x.identifier) for x in runtime_layers
                if not Path(str(x.realPath or x.identifier)).is_relative_to(ROOT / 'runtime')]
    external += [str(x) for x in runtime_assets
                 if str(x) not in runtime_materials
                 and str(x) not in runtime_materials.values()
                 and str(x) not in localized_assets]
    assert not external, 'Project dependencies outside migration: ' + str(external)
    atomic_json(ROOT / 'asset-manifest.json', {'project_assets': localized_assets,
                                             'isaac_builtin_materials': runtime_materials})
    stage = Usd.Stage.Open(str(runtime_stage_path))
    assert stage, 'Cannot open original stage'
    required = {p: bool(stage.GetPrimAtPath(p)) for p in REQUIRED}
    assert all(required.values()), required
    # Remove transient graphs from the in-memory runtime copy. Deactivating
    # old SDG parents prevents Isaac from defining its new annotator nodes at
    # those paths. Never save these edits to the copied original USD.
    stage.SetEditTarget(stage.GetRootLayer())
    muted = []
    graph_paths = []
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            if 'script' in attr.GetName().lower() and attr.Get():
                raise ValueError('Scripted stage requires separate review: ' + str(prim.GetPath()))
        if prim.GetTypeName() in ('OmniGraph', 'OmniGraphNode'):
            graph_paths.append(str(prim.GetPath()))
    for graph_path in graph_paths:
        prim = stage.GetPrimAtPath(graph_path)
        if prim:
            muted.append(graph_path)
            assert stage.RemovePrim(graph_path), 'Cannot remove old graph: ' + graph_path
    # Saved render products are runtime outputs, not workcell geometry.
    if stage.GetPrimAtPath('/Render'):
        assert stage.RemovePrim('/Render')
    assert all(stage.GetPrimAtPath(p) for p in REQUIRED), 'Workcell changed during graph cleanup'
    stage.SetEditTarget(stage.GetSessionLayer())
    cache = UsdUtils.StageCache.Get()
    stage_id = cache.Insert(stage)
    context = omni.usd.get_context()
    attached = []
    assert context.attach_stage_with_callback(stage_id.ToLongInt(), lambda ok, error: attached.append((ok, error)))
    deadline = time.monotonic() + 60
    while not attached and time.monotonic() < deadline:
        app.update()
    assert attached and attached[0][0], 'Cannot attach original stage: ' + str(attached)
    timeline = omni.timeline.get_timeline_interface()
    timeline.stop()
    cameras = [str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdGeom.Camera)]
    assert cameras, 'Existing stage has no camera'
    camera = next((p for p in cameras if 'observer' in p.lower()), cameras[0])
    product = rep.create.render_product(camera, (1280, 720))
    rgb = rep.AnnotatorRegistry.get_annotator('rgb')
    rgb.attach([product])
    for _ in range(24):
        rep.orchestrator.step(rt_subframes=4, delta_time=0.0, pause_timeline=True)
        frame = np.asarray(rgb.get_data())
        if frame.shape[:2] == (720, 1280) and frame.std() > 1:
            break
    assert frame.shape[:2] == (720, 1280) and frame.std() > 1, 'No rendered RGB frame'
    assert not timeline.is_playing(), 'Timeline unexpectedly playing'
    assert digest(path) == expected, 'Original stage was modified'
    assert cv2.imwrite(str(PUBLIC / 'frame.png'), cv2.cvtColor(frame[:, :, :3], cv2.COLOR_RGB2BGR))
    state.update(state='ENVIRONMENT_READY', stage_preserved=True, frame=True,
                 captured_at=time.time(), stage_sha256=expected, required_prims=required,
                 camera=camera, muted_graph_count=len(muted),
                 unresolved_assets=0, dependency_layers=len(layers),
                 dependency_assets=len(assets), timeline='stopped',
                 localized_asset_count=len(localized_assets),
                 project_assets_localized=True, runtime_materials=list(runtime_materials),
                 runtime_version=Path('/isaac-sim/VERSION').read_text().strip())
    atomic_json(ROOT / 'render-verification.json', state)
    atomic_json(PUBLIC / 'state.json', state)
    print('S2A_ENVIRONMENT_READY ' + json.dumps(state), flush=True)
except Exception as exc:
    state.update(state='MIGRATION_FAILED', error_type=type(exc).__name__)
    atomic_json(PUBLIC / 'state.json', state)
    traceback.print_exc()
    raise
finally:
    if app:
        app.close()
