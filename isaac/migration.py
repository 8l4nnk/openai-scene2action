"""Preserve the existing S05 environment and verify it in the new runtime.

The original USD and source files are copied byte-for-byte. Rendering opens
that USD; it never constructs a replacement workcell or runs legacy agents.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil

SOURCE = Path('/workspace/environments/isaac_tools_worker_clone_yq1s3wwmt41ng1_20260929')
ROOT = Path('/workspace/scene2action_migrated_20261009')
REQUIRED = ('/World/XArm6', '/World/Worker', '/World/Tools/knife',
            '/World/Tools/wrench',
            '/World/Workcell/TableFrame/Objects/S05_sphere_red',
            '/World/Workcell/TableFrame/Objects/S05_sphere_blue')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def copy_verified(source, destination):
    """Refuse changed destinations and symlinks; never overwrite an original."""
    if source.is_symlink() or destination.is_symlink():
        raise ValueError('Symlink is not a migration file')
    for parent in destination.parents:
        if parent.is_symlink():
            raise ValueError('Symlink in destination path')
    expected = digest(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        with source.open('rb') as src, destination.open('xb') as dst:
            shutil.copyfileobj(src, dst)
    if digest(destination) != expected:
        raise ValueError('Source/destination hash mismatch: ' + str(destination))
    return expected


def migrate(source=SOURCE, root=ROOT):
    if (source.resolve() == root.resolve() or root.resolve().is_relative_to(source.resolve())
            or source.resolve().is_relative_to(root.resolve())):
        raise ValueError('Migration destination must be separate from the original')
    if source.is_symlink() or root.is_symlink():
        raise ValueError('Migration roots must not be symlinks')
    manifest = {}
    for folder in ('scene', 'assets', 'source'):
        for path in sorted((source / folder).rglob('*')):
            if path.is_symlink():
                raise ValueError('Symlink in source snapshot')
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            # Preserve every environment artifact type, including MDL, URDF,
            # YAML and uncommon texture formats; omit private tool settings.
            if any(part.startswith('.') for part in path.relative_to(source).parts):
                continue
            if path.name.upper() in {'CLAUDE.MD', 'GEMINI.MD'}:
                continue
            rel = path.relative_to(source)
            manifest[rel.as_posix()] = copy_verified(path, root / 'original' / rel)
    for name in ('environment.json', 'run.sh', 'verify_saved_scene.py'):
        path = source / name
        if path.is_file():
            manifest[name] = copy_verified(path, root / 'original' / name)
    if 'scene/environment.usdc' not in manifest:
        raise ValueError('Existing environment.usdc is required')
    record = {'source': str(source), 'destination': str(root / 'original'),
              'files': manifest, 'file_count': len(manifest),
              'original_stage_sha256': manifest['scene/environment.usdc'],
              'source_modified': False, 'legacy_scripts_executed': False}
    atomic_json(root / 'manifest.json', record)
    return record


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


if __name__ == '__main__':
    record = migrate()
    print('S2A_MIGRATED ' + json.dumps({k: v for k, v in record.items() if k != 'files'}), flush=True)
