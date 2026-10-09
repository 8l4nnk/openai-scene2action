import base64
import io
import math
from copy import deepcopy

from PIL import Image, ImageDraw


CLEARANCE = 0.045
SPEED = 0.4  # Normalized simulator units per second; not robot metres.


def segment_blocked(start, end, obstacles, radius):
    """Conservative swept disk vs expanded AABBs, including contact."""
    if not all(math.isfinite(v) for v in (*start, *end, radius)):
        return True
    if any(v < radius or v > 1 - radius for v in (*start, *end)):
        return True
    for x0, y0, x1, y1 in obstacles:
        low, high = 0.0, 1.0
        for a, b, lower, upper in zip(start, end, (x0-radius, y0-radius), (x1+radius, y1+radius)):
            delta = b-a
            if abs(delta) < 1e-12:
                # Tiny motion can still cross the boundary; include both endpoints.
                if max(a,b) < lower or min(a,b) > upper:
                    low, high = 1.0, 0.0
                    break
            else:
                t0, t1 = sorted(((lower-a)/delta, (upper-a)/delta))
                low, high = max(low, t0), min(high, t1)
        if low <= high:
            return True
    return False


def make_world(contract, now, revision):
    return dict(
        position=[0.12, 0.5],
        objects={k: [v.x, v.y] for k, v in contract.objects.items()},
        targets={k: [v.x, v.y] for k, v in contract.targets.items()},
        obstacles=[], held=None, revision=revision, observed_at=now,
        sensor_online=True, coordinate_frame='sim_table', unit='normalized',
    )


def expand(actions, world):
    commands = []
    positions = deepcopy(world['objects'])
    for action in actions:
        source = positions[action.object_id]
        target = world['targets'][action.target_id]
        for phase, point in [('approach', source), ('grasp', source), ('transfer', target), ('release', target)]:
            commands.append(dict(phase=phase, object_id=action.object_id,
                                 target_id=action.target_id, position=list(point)))
        positions[action.object_id] = list(target)
    return commands


def validate_commands(commands, contract, world):
    # Independent expected sequence derived from the trusted contract.
    if len(commands) != 4 * len(contract.steps):
        return False
    for index, action in enumerate(contract.steps):
        source, target = world['objects'][action.object_id], world['targets'][action.target_id]
        for offset, (phase, point) in enumerate(zip(
                ('approach', 'grasp', 'transfer', 'release'), (source, source, target, target))):
            command = commands[index*4+offset]
            if command != dict(phase=phase, object_id=action.object_id,
                               target_id=action.target_id, position=list(point)):
                return False
    return True


def path_clear(commands, world):
    position = world['position']
    for command in commands:
        if segment_blocked(position, command['position'], world['obstacles'], CLEARANCE):
            return False
        position = command['position']
    return True


def camera_png(world):
    image = Image.new('RGB', (800, 600), '#101e2b')
    draw = ImageDraw.Draw(image)
    def xy(point):
        return int(point[0]*760+20), int(point[1]*560+20)
    for i in range(11):
        draw.line((20+i*76, 20, 20+i*76, 580), fill='#213444')
        draw.line((20, 20+i*56, 780, 20+i*56), fill='#213444')
    for key, point in world['targets'].items():
        x, y = xy(point)
        draw.rectangle((x-40, y-30, x+40, y+30), outline='#41d5b0', width=3)
        draw.text((x-30, y+35), key, fill='white')
    colors = ['#fa846b', '#79b6ff']
    for index, (key, point) in enumerate(world['objects'].items()):
        x, y = xy(point)
        draw.ellipse((x-17, y-17, x+17, y+17), fill=colors[index % 2])
        draw.text((x-20, y-35), key, fill='white')
    for box in world['obstacles']:
        draw.rectangle((*xy(box[:2]), *xy(box[2:])), fill='#876342')
    x, y = xy(world['position'])
    draw.ellipse((x-10, y-10, x+10, y+10), outline='white', width=3)
    draw.text((24, 24), 'SIMULATED CAMERA / normalized 2D / not a real robot', fill='#9eb3c5')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def camera_data_url(world):
    return 'data:image/png;base64,' + base64.b64encode(camera_png(world)).decode('ascii')
