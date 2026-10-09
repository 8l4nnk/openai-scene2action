"""Create a pinned local copy of the existing runtime, adding capture integrity."""
import hashlib
from pathlib import Path

SOURCE = Path('/workspace/codex_jaewoo_20261009/experiment-env/runtime/isaac_ros2_control_entry_local.py')
EXPECTED = 'd89abcf7fcfd322e63b0be5088170a1546f96730fa6bdded13a74a0f853a9f42'


def prepare(source, destination, expected):
    if any(p.is_symlink() for p in (source,destination,*destination.parents)):
        raise ValueError('Symlink rejected')
    data = source.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Existing runtime changed; review required')
    text = data.decode().replace('\r\n','\n')
    marker = '"rgb_sha256": digest,'
    assert text.count(marker) == 1
    text = text.replace(marker, marker + '''
            "capture_file_sha256": {
                "rgb": hashlib.sha256((ARGS.run_dir / "latest_rgb.jpg").read_bytes()).hexdigest(),
                "depth": hashlib.sha256((ARGS.run_dir / "latest_depth.npy").read_bytes()).hexdigest(),
            },''')
    # This normal-only instance does not accept visual-card or episode-reset requests.
    for call in ('node.create_service(Trigger, "/scene2action/apply_visual_card", request_visual_card)',
                 'node.create_service(Trigger, "/scene2action/reset_episode_objects", request_episode_reset)'):
        assert text.count(call) == 1
        text = text.replace(call,'pass  # Normal validation: no external scene mutation service')
    compile(text,str(destination),'exec')
    if destination.exists():
        if destination.read_text() != text:
            raise ValueError('Refusing to overwrite another runtime')
    else:
        with destination.open('x',encoding='utf-8',newline='\n') as f:
            f.write(text)
    return hashlib.sha256(text.encode()).hexdigest()


if __name__ == '__main__':
    print(prepare(SOURCE,Path(__file__).with_name('normal_isaac_runtime.py'),EXPECTED))
