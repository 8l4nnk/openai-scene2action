"""Explicit source allowlist plus the user-approved, hashed demo corpus."""
import hashlib
import json
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    output = ROOT / '.data/aws-deploy/release.tar.gz'
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [ROOT/'pyproject.toml', ROOT/'uv.lock', ROOT/'native/geometry.cpp',
             ROOT/'scripts/build_native.py']
    for directory in ('scene2action', 'contracts', 'policies', 'deploy/aws'):
        files.extend(p for p in (ROOT/directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts
                     and p.suffix in ('.py', '.html', '.css', '.js', '.json', '.txt', '.sh'))
    if any(p.is_symlink() for p in files):
        raise ValueError('Symlinks cannot be deployed')
    demo = ROOT/'demo'
    if demo.is_symlink() or demo.resolve() != ROOT.resolve()/'demo':
        raise ValueError('Invalid demo directory')
    manifest_path = demo/'manifest.json'
    if manifest_path.is_symlink() or not manifest_path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('Invalid demo manifest path')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for name, expected in manifest['files'].items():
        path=demo/name
        if path.is_symlink() or not path.resolve().is_relative_to(demo.resolve()):
            raise ValueError('Invalid demo path')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('Demo hash mismatch')
        files.append(path)
    files.append(manifest_path)
    with tarfile.open(output, 'w:gz') as archive:
        for path in sorted(set(files)):
            archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)
    print(f'{len(set(files))} source files; SHA256 {hashlib.sha256(output.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
