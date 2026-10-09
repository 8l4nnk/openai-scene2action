import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('isaac_migration', Path(__file__).parents[1] / 'isaac/migration.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_migration_preserves_original_and_detects_changed_destination(tmp_path):
    source, dest = tmp_path / 'source', tmp_path / 'migration'
    (source / 'scene').mkdir(parents=True)
    stage = source / 'scene/environment.usdc'
    stage.write_bytes(b'original stage')
    (source / '.env').write_text('PRIVATE')
    (source / 'assets').mkdir()
    (source / 'assets/texture.exr').write_bytes(b'exr')
    result = m.migrate(source, dest)
    assert result['file_count'] == 2
    assert (dest / 'original/assets/texture.exr').read_bytes() == b'exr'
    assert stage.read_bytes() == b'original stage'
    assert not (dest / 'original/.env').exists()
    assert m.migrate(source, dest) == result
    (dest / 'original/scene/environment.usdc').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        m.migrate(source, dest)


def test_missing_original_stage_and_nested_destination_rejected(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    with pytest.raises(ValueError, match='separate'):
        m.migrate(source, source / 'copy')
    with pytest.raises(ValueError, match='separate'):
        m.migrate(source, tmp_path)
    with pytest.raises(ValueError, match='required'):
        m.migrate(source, tmp_path / 'migration')
