import hashlib
import pytest
from isaac.prepare_l4_runtime import prepare


def test_pinned_copy_preserves_original_and_disables_scene_mutators(tmp_path):
    src = tmp_path/'source.py'
    dst = tmp_path/'copy.py'
    original = '''d = {"rgb_sha256": digest,}
node.create_service(Trigger, "/scene2action/apply_visual_card", request_visual_card)
node.create_service(Trigger, "/scene2action/reset_episode_objects", request_episode_reset)
'''
    src.write_text(original)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    prepare(src,dst,digest)
    assert src.read_text() == original
    assert 'capture_file_sha256' in dst.read_text()
    assert 'create_service' not in dst.read_text()
    prepare(src,dst,digest)
    with pytest.raises(ValueError):
        prepare(src,dst,'0'*64)
