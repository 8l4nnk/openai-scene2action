"""Geometry-only evaluation; SI units, quaternion order w,x,y,z."""
import numpy as np


def rotation(q):
    w, x, y, z = np.asarray(q) / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def extents(shape, quaternion):
    r = rotation(quaternion)
    if shape == 'sphere':
        return np.full(3, .020)
    if shape == 'cube':
        return np.abs(r) @ np.full(3, .020)
    axis = r[:, 2]
    return .020*np.abs(axis) + .0175*np.sqrt(np.maximum(0., 1-axis*axis))


def diameter(positions):
    p = np.asarray(positions)
    return float(np.linalg.norm(p[:, None, :] - p[None, :, :], axis=-1).max())


def placement(shape, pose, target, zone_center, settle_positions, slot=False):
    p = np.asarray(pose['position_table_m'])
    q = pose['quaternion_wxyz']
    e = extents(shape, q)
    clearance = .055 - np.abs(p[:2] - np.asarray(zone_center)[:2]) - e[:2]
    tilt = float(np.degrees(np.arccos(np.clip(rotation(q)[2, 2], -1, 1))))
    stable = diameter(settle_positions)
    slot_error = float(np.linalg.norm(p[:2]-np.asarray(target)[:2]))
    checks = dict(whole_projection_with_10mm_margin=bool(np.all(clearance >= .010)),
                  stable_2s=stable <= .005,
                  upright=shape == 'sphere' or tilt < 10.,
                  supported_on_table=abs(float(p[2]-e[2])) < .002,
                  assigned_slot=not slot or slot_error <= .005)
    return dict(checks=checks, success=all(checks.values()),
                zone_clearance_m=clearance.tolist(), tilt_deg=tilt,
                projected_half_extents_m=e.tolist(), stability_diameter_m=stable,
                target_xy_error_m=slot_error, final_pose=pose)
