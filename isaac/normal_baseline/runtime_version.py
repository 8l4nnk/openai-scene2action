"""Identify the runtime from its installation, supporting wheel and binary images."""
import importlib.metadata
import re
from pathlib import Path


def version_from_file(path):
    if path.stat().st_size>256:
        raise ValueError('Invalid runtime VERSION file')
    value=path.read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'6\.1\.0(?:-[A-Za-z0-9.-]+)?(?:\+[A-Za-z0-9.-]+)?',value):
        raise ValueError('Required Isaac 6.1.0 binary runtime')
    return {'version':value,'source':'binary_VERSION'}


def runtime_version():
    try:
        value=importlib.metadata.version('isaacsim')
    except importlib.metadata.PackageNotFoundError:
        return version_from_file(Path('/isaac-sim/VERSION'))
    if value!='6.1.0.0':
        raise ValueError('Required Isaac 6.1.0.0 wheel runtime')
    return {'version':value,'source':'wheel_metadata'}
