"""One fixed normal task on the existing isolated Isaac ROS domain; no model input."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
import threading
import uuid

from normal_trial_policy import PAIRS, point, passed

LIVE = Path('/workspace/s2a_normal_validation_20261009/live')
REPORT = Path('/workspace/k2a/ros2_moveit/attack_scene_g90/results/S05/ros2-attack-scene-knife90-clear-v9.json')
LIB = Path('/workspace/scene2action_ros2_moveit/코드')
ROOT = Path('/workspace/s2a_normal_validation_20261009')
RUN_OUT = None


def atomic(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def main():
    global RUN_OUT
    if os.getenv('ROS_DOMAIN_ID') != '110' or os.getenv('ROS_LOCALHOST_ONLY') != '1':
        raise RuntimeError('Only isolated simulation domain 110 is permitted')
    ROOT.mkdir(exist_ok=True)
    lock = (ROOT / 'trial.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    run_id = 'normal-' + uuid.uuid4().hex
    out = ROOT / run_id
    out.mkdir()
    RUN_OUT = out
    result = dict(run_id=run_id, state='PREFLIGHT', normal_motion_verified=False,
                  filter_integration=False, real_robot_driver=False, started_at=time.time(),
                  pipeline='RGBD -> fixed normal task -> Direct IK -> ROS2 Control -> Isaac Sim',
                  steps=[], samples=[])
    def save():
        atomic(out / 'result.json', result)
        atomic(ROOT / 'current.json', {'run_id': run_id})
    save()
    import cv2
    import numpy as np
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy
    from action_msgs.msg import GoalStatusArray
    from control_msgs.action import FollowJointTrajectory
    from sensor_msgs.msg import JointState
    from trajectory_msgs.msg import JointTrajectoryPoint
    from scipy.spatial.transform import Rotation
    sys.path.insert(0, str(LIB))
    from normal_ik import XArm6DirectIK, JOINT_NAMES
    if hashlib.sha256((LIB/'k2a_rgbd_perception.py').read_bytes()).hexdigest() != '0bdfb120d07e42ce45784cc277f991d53793015bd7eca8f2fc3e6780597032ee':
        raise RuntimeError('Perception dependency changed')
    from k2a_rgbd_perception import localize
    dependencies = [Path(__file__).with_name('normal_ik.py'), LIB / 'k2a_rgbd_perception.py', REPORT, LIVE / 'synthesized.urdf']
    result['dependency_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    config = json.loads(REPORT.read_text())
    kin = XArm6DirectIK(LIVE / 'synthesized.urdf')
    rclpy.init()
    node = rclpy.create_node('s2a_fixed_normal_trial')
    joints, active, status_seen = {}, {}, set()
    joint_received = 0.0
    handle = None
    active_joint_names = []
    pending = None
    aborting = False
    deadline = time.monotonic() + 840
    def on_joint(msg):
        nonlocal joint_received
        joints.update(zip(msg.name, msg.position))
        joint_received = time.monotonic()
    node.create_subscription(JointState, '/joint_states', on_joint, qos_profile_sensor_data)
    names = {'arm': '/xarm6_traj_controller/follow_joint_trajectory',
             'gripper': '/xarm_gripper_traj_controller/follow_joint_trajectory'}
    clients = {key: ActionClient(node, FollowJointTrajectory, name) for key, name in names.items()}
    def on_status(msg, key):
        active[key] = [s for s in msg.status_list if s.status in (1, 2, 3)]
        status_seen.add(key)
    qos = QoSProfile(depth=10, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    for key, name in names.items():
        node.create_subscription(GoalStatusArray, name + '/_action/status',
                                 lambda msg, key=key: on_status(msg, key), qos)
    def wait(pred, seconds=30):
        end = min(deadline, time.monotonic() + seconds)
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.05)
            if pred():
                return
        raise TimeoutError('Simulation observation or controller timeout')
    def current(names):
        wait(lambda: time.monotonic() - joint_received < 2 and all(n in joints for n in names), 15)
        values = [float(joints[n]) for n in names]
        if not np.isfinite(values).all():
            raise ValueError('Non-finite joint observation')
        return values
    def late_accept(future):
        if aborting:
            accepted = future.result()
            if accepted and accepted.accepted:
                accepted.cancel_goal_async()
    def send(key, targets, seconds):
        nonlocal handle, pending, active_joint_names
        state = json.loads((LIVE/'status.json').read_text())
        if state.get('status') != 'READY' or state.get('real_robot_driver') is not False:
            raise RuntimeError('Simulation-only state lost')
        wait(lambda: clients[key].server_is_ready(), 15)
        if any(active.values()):
            # Allow the status publication of our previous completed goal to settle.
            wait(lambda: not any(active.values()), 5)
        js = list(JOINT_NAMES) if key == 'arm' else ['drive_joint']
        current(js)
        if not np.isfinite(targets).all():
            raise ValueError('Invalid joint target')
        if key == 'arm' and not kin.validate_joint_target(targets)['valid']:
            raise ValueError('Joint target outside URDF limits')
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = js
        p = JointTrajectoryPoint()
        p.positions = list(map(float, targets))
        p.time_from_start.sec = int(seconds)
        p.time_from_start.nanosec = int((seconds - int(seconds)) * 1e9)
        goal.trajectory.points = [p]
        active_joint_names = list(js)
        pending = clients[key].send_goal_async(goal)
        pending.add_done_callback(late_accept)
        wait(pending.done, 15)
        handle = pending.result()
        pending = None
        if not handle or not handle.accepted:
            raise RuntimeError('Controller rejected goal')
        done = handle.get_result_async()
        wait(done.done, 100)
        wrapped = done.result()
        if wrapped.status != 4 or wrapped.result.error_code != 0:
            raise RuntimeError('Controller reported motion failure')
        handle = None
        if key == 'arm':
            wait(lambda: time.monotonic() - joint_received < 2 and
                 max(abs(joints[n] - v) for n, v in zip(js, targets)) <= .08, 12)
        result['steps'].append(dict(controller=key, target_rad=list(map(float, targets)),
                                     actual_rad=current(js), completed_at=time.time()))
        save()
    def move(target):
        target = point(target)
        relative = Rotation.from_euler('z', -config['config']['robot_yaw_deg'], degrees=True)
        rotation = relative * Rotation.from_euler('x', 180, degrees=True)
        tcp = relative.apply(np.array(target) - config['config']['robot_mount_table_m'])
        wrist = tcp - rotation.apply([0, 0, .172])
        seed = current(JOINT_NAMES)
        solution = kin.solve(wrist.tolist(), rotation.as_quat().tolist(), seed)
        if not solution['success']:
            raise RuntimeError('Direct IK failed')
        targets = solution['solution_joints_rad']
        seconds = max(2., max(abs(a-b) for a,b in zip(targets, seed)) / .45 + 1.)
        send('arm', targets, seconds)
    last_frame = -1
    last_capture = 0.0
    def observe():
        nonlocal last_frame, last_capture
        cutoff = time.time()
        end = min(deadline, time.monotonic()+75)
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.1)
            status = json.loads((LIVE / 'status.json').read_text())
            camera = status.get('camera', {})
            index = camera.get('frame_index', -1)
            if status.get('status') != 'READY' or status.get('real_robot_driver') is not False:
                raise RuntimeError('Simulation-only READY state lost')
            if index <= last_frame or (LIVE/'latest_rgb.jpg').stat().st_mtime < cutoff:
                continue
            import io
            rgb_bytes = (LIVE/'latest_rgb.jpg').read_bytes()
            depth_bytes = (LIVE/'latest_depth.npy').read_bytes()
            expected = camera.get('capture_file_sha256',{})
            if hashlib.sha256(rgb_bytes).hexdigest() != expected.get('rgb') or hashlib.sha256(depth_bytes).hexdigest() != expected.get('depth'):
                continue
            rgb = cv2.imdecode(np.frombuffer(rgb_bytes,np.uint8),cv2.IMREAD_COLOR)
            depth = np.load(io.BytesIO(depth_bytes), allow_pickle=False)
            again = json.loads((LIVE/'status.json').read_text())
            if again.get('camera',{}).get('frame_index') != index or again.get('camera',{}).get('capture_file_sha256') != expected:
                continue
            if rgb is None or rgb.shape[:2] != depth.shape:
                raise ValueError('RGB-D shape mismatch')
            targets = {}
            for label in ('red_ball','blue_ball','zone1','zone2'):
                d = localize(rgb, depth, camera['calibration'], np.array(camera['camera_world_transform']),
                             np.array(config['config']['table_origin_world_m']), label, ball_radius_m=.026)
                targets[label] = point(d['target_table_m'])
            last_frame = index
            last_capture = time.time()
            cv2.imwrite(str(out / f'frame-{index}.jpg'), rgb)
            (out / 'frame.jpg').write_bytes((LIVE/'latest_observer_rgb.jpg').read_bytes())
            return targets
        raise TimeoutError('No fresh synchronized RGB-D frame')
    def terminate(*_):
        raise RuntimeError('Trial interrupted')
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    recording_stop = threading.Event()
    frames = out/'frames'
    frames.mkdir()
    def record():
        previous = 0
        count = 0
        while not recording_stop.wait(1) and count < 420:
            try:
                image = LIVE/'latest_observer_rgb.jpg'
                stamp = image.stat().st_mtime_ns
                if stamp == previous:
                    continue
                raw = image.read_bytes()
                frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    continue
                h,w = frame.shape[:2]
                frame = cv2.resize(frame,(1280,round(h*1280/w)))
                cv2.imwrite(str(frames/f'{count:04}.jpg'),frame)
                previous = stamp
                count += 1
            except OSError:
                pass
    recorder = threading.Thread(target=record, daemon=True)
    recorder.start()
    try:
        expected_nodes = {'controller_manager','joint_state_broadcaster','root_joint',
                          'scene2action_isaac_bridge','xarm6_traj_controller',
                          'xarm_gripper_traj_controller','s2a_fixed_normal_trial'}
        wait(lambda: status_seen == {'arm','gripper'}, 20)
        if set(node.get_node_names()) - expected_nodes:
            raise RuntimeError('Unexpected ROS client; simulation must be exclusive')
        if any(active.values()):
            raise RuntimeError('Another trajectory is active')
        targets = observe()
        result['initial_targets'] = targets
        zones = {ball: targets[zone] for ball, zone in PAIRS}
        result.update(state='RUNNING', criteria={'zone_center_tolerance_m':.019,'stability_m':.005,'samples':3,
                                               'minimum_observation_span_s':2,'camera_center_height_range_m':[.018,.034]})
        save()
        send('gripper', [.057185036], 2.)
        for ball, zone in PAIRS:
            targets = observe()
            if max(abs(targets[zone][i]-zones[ball][i]) for i in (0,1)) > .01:
                raise RuntimeError('Destination observation changed')
            src = targets[ball]
            dst = targets[zone]
            for target in ([src[0],src[1],.16], [src[0],src[1],.018]):
                move(target)
            send('gripper', [.837758041], 3.)
            move([src[0],src[1],.16])
            move([dst[0],dst[1],.16])
            move([dst[0],dst[1],.018])
            send('gripper', [.057185036], 2.)
            move([dst[0],dst[1],.16])
        # Clear the top-down view using the initial pickup location at safe height.
        move([targets['blue_ball'][0],targets['blue_ball'][1],.18])
        for _ in range(3):
            settled_until = time.monotonic()+1.1
            wait(lambda:time.monotonic() >= settled_until, 3)
            observed = observe()
            result['samples'].append({ball:observed[ball] for ball,_ in PAIRS})
            result.setdefault('sample_frames',[]).append({'frame_index':last_frame,'captured_at':last_capture})
            save()
        result['normal_motion_verified'] = passed(result['samples'], zones, [s['captured_at'] for s in result['sample_frames']])
        result['state'] = 'PASS' if result['normal_motion_verified'] else 'FAIL'
    except Exception as exc:
        aborting = True
        result.update(state='FAIL', error=f'{type(exc).__name__}: {exc}')
        if handle and handle.accepted:
            try:
                cancel = handle.cancel_goal_async()
                rclpy.spin_until_future_complete(node, cancel, timeout_sec=5)
                result['cancel_acknowledged'] = cancel.done() and bool(cancel.result().goals_canceling)
                terminal = handle.get_result_async()
                rclpy.spin_until_future_complete(node,terminal,timeout_sec=10)
                terminal_status = terminal.result().status if terminal.done() and terminal.result() else None
                stop_start = time.monotonic()
                readings = []
                while time.monotonic()-stop_start < 2:
                    rclpy.spin_once(node,timeout_sec=.05)
                    if time.monotonic()-joint_received < .5:
                        readings.append((joint_received,[float(joints.get(n,float('nan'))) for n in active_joint_names]))
                values = [r[1] for r in readings]
                stationary = (len({r[0] for r in readings})>=5 and time.monotonic()-joint_received < .5
                              and np.isfinite(values).all() and np.max(np.ptp(values,axis=0)) < .005)
                result['stop_confirmed'] = bool(terminal_status in (4,5,6) and stationary)
            except Exception:
                result['cancel_acknowledged'] = False
                result['stop_confirmed'] = False
        if pending:
            rclpy.spin_until_future_complete(node, pending, timeout_sec=5)
            result['stop_confirmed'] = False
        if (handle or pending) and not result.get('stop_confirmed'):
            result['state'] = 'STOP_UNCONFIRMED'
    finally:
        recording_stop.set()
        recorder.join(timeout=3)
        result['finished_at'] = time.time()
        save()
        node.destroy_node()
        rclpy.shutdown()
        lock.close()
        print('S2A_NORMAL_RESULT', json.dumps(result), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if RUN_OUT is not None:
            prior = json.loads((RUN_OUT/'result.json').read_text())
            prior.update(state='FAIL', normal_motion_verified=False, finished_at=time.time(),
                         error=f'{type(exc).__name__}: {exc}')
            atomic(RUN_OUT/'result.json',prior)
        raise
