"""Read-only bootstrap inventory; no simulator, robot or network service is started."""
import json
import sys
from pathlib import Path


def main():
    root = Path('/workspace/environments/isaac_tools_worker_clone_yq1s3wwmt41ng1_20260929')
    stage = root / 'runs/results/S05/openvla-base-topview-normal-20260929-01.usda'
    candidates = [root / 'run.sh', root / 'code', root / 'configs',
                  Path('/workspace/setup/isaac61/code'), Path('/isaac-sim/python.sh')]
    print(json.dumps({'kind': 'S2A_INVENTORY', 'python': sys.version.split()[0],
                      'stage_exists': stage.is_file(),
                      'paths': {str(p): p.exists() for p in candidates},
                      'root_entries': sorted(p.name for p in root.iterdir())[:100] if root.is_dir() else [],
                      'setup_code_filenames': sorted(p.name for p in Path('/workspace/setup/isaac61/code').glob('*.py'))[:80],
                      'code_filenames': sorted(p.name for p in (root / 'code').glob('*.py'))[:80]},
                     sort_keys=True), flush=True)
    if stage.is_file() and stage.stat().st_size < 1024 * 1024:
        lines = stage.read_text(encoding='utf-8').splitlines()
        print(json.dumps({'kind': 'S2A_STAGE_METADATA',
                          'camera_declarations': [s.strip() for s in lines if 'def Camera ' in s],
                          'graph_marker_lines': [s.strip()[:300] for s in lines if any(
                              marker in s.lower() for marker in ('omnigraph', 'scriptnode', 'ros2', 'python:'))][:40],
                          'has_graph_or_script_markers': any(
                              s.lower().find(marker) >= 0 for s in lines
                              for marker in ('omnigraph', 'scriptnode', 'ros2', 'python:'))}), flush=True)


if __name__ == '__main__':
    main()
