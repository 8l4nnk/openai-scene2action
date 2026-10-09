#!/usr/bin/env python3
"""MoveIt-free xArm6 kinematics from the official xarm_description URDF.

The solver reads the six revolute joints from the same xarm_description model
previously used to configure the planner, then uses deterministic bounded
nonlinear least squares. It does not call MoveIt, Isaac articulation APIs,
scene object poses, or collision planners.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


JOINT_NAMES = tuple(f"joint{index}" for index in range(1, 7))

def _numbers(value: str | None, default: tuple[float, ...]) -> np.ndarray:
    if not value:
        return np.asarray(default, dtype=float)
    result = np.asarray([float(item) for item in value.split()], dtype=float)
    if result.shape != (len(default),):
        raise ValueError(f"unexpected vector size: {value!r}")
    return result


def _origin_matrix(origin: ET.Element | None) -> np.ndarray:
    xyz = _numbers(origin.get("xyz") if origin is not None else None, (0.0, 0.0, 0.0))
    rpy = _numbers(origin.get("rpy") if origin is not None else None, (0.0, 0.0, 0.0))
    transform = np.eye(4, dtype=float)
    transform[:3, :3] = Rotation.from_euler("xyz", rpy).as_matrix()
    transform[:3, 3] = xyz
    return transform


def _axis_rotation(axis: np.ndarray, angle: float) -> np.ndarray:
    transform = np.eye(4, dtype=float)
    transform[:3, :3] = Rotation.from_rotvec(axis * float(angle)).as_matrix()
    return transform


class XArm6DirectIK:
    """Six-joint FK/IK using the official xArm6 description and limits."""

    def __init__(self, urdf_path: Path):
        root = ET.parse(urdf_path).getroot()
        self.urdf_path = Path(urdf_path)
        self.origins: list[np.ndarray] = []
        self.axes: list[np.ndarray] = []
        lower, upper, velocity = [], [], []
        for name in JOINT_NAMES:
            joint = root.find(f"./joint[@name='{name}']")
            if joint is None or joint.get("type") not in {"revolute", "continuous"}:
                raise ValueError(f"missing revolute URDF joint: {name}")
            self.origins.append(_origin_matrix(joint.find("origin")))
            axis = _numbers(
                joint.find("axis").get("xyz") if joint.find("axis") is not None else None,
                (1.0, 0.0, 0.0),
            )
            norm = float(np.linalg.norm(axis))
            if norm < 1e-9:
                raise ValueError(f"zero URDF axis: {name}")
            self.axes.append(axis / norm)
            limit = joint.find("limit")
            if limit is None:
                raise ValueError(f"missing URDF limit: {name}")
            lower.append(float(limit.get("lower", -2.0 * math.pi)))
            upper.append(float(limit.get("upper", 2.0 * math.pi)))
            velocity.append(float(limit.get("velocity", 1.0)))
        self.urdf_declared_lower = np.asarray(lower, dtype=float)
        self.urdf_declared_upper = np.asarray(upper, dtype=float)
        # The same official UFACTORY URDF supplies both kinematic origins and
        # mechanical limits.  Do not replace its bounded xArm6 joints with
        # synthetic +/-2*pi ranges merely to accommodate a drifting simulator.
        self.lower = self.urdf_declared_lower.copy()
        self.upper = self.urdf_declared_upper.copy()
        self.joint_limit_source = "official_ufactory_xarm6_urdf_joint_limits"
        self.velocity = np.asarray(velocity, dtype=float)

    def forward(self, joints: np.ndarray | list[float]) -> np.ndarray:
        values = np.asarray(joints, dtype=float)
        if values.shape != (6,):
            raise ValueError("xArm6 FK requires six joints")
        transform = np.eye(4, dtype=float)
        for origin, axis, value in zip(self.origins, self.axes, values):
            transform = transform @ origin @ _axis_rotation(axis, float(value))
        return transform

    @staticmethod
    def pose_error(transform: np.ndarray, target: np.ndarray) -> tuple[float, float]:
        position_error = float(np.linalg.norm(transform[:3, 3] - target[:3, 3]))
        rotation_error = float(np.linalg.norm(Rotation.from_matrix(
            target[:3, :3].T @ transform[:3, :3]).as_rotvec()))
        return position_error, rotation_error

    def solve(self, position_xyz: list[float], quaternion_xyzw: list[float],
              seed: list[float] | np.ndarray) -> dict:
        target = np.eye(4, dtype=float)
        target[:3, :3] = Rotation.from_quat(quaternion_xyzw).as_matrix()
        target[:3, 3] = np.asarray(position_xyz, dtype=float)
        # ``least_squares`` below deliberately keeps solutions a tiny distance
        # inside the mechanical bounds.  Use those same interior limits for
        # every solver seed; clipping a live joint exactly to ``self.lower`` or
        # ``self.upper`` makes that seed invalid against the stricter bounds.
        # This changes only the numerical initial guess, never the requested
        # Cartesian target or a resulting joint target.
        solver_lower = self.lower + 1e-7
        solver_upper = self.upper - 1e-7
        raw_seed = np.asarray(seed, dtype=float)
        if raw_seed.shape != (6,):
            raise ValueError("xArm6 IK seed requires six joints")
        seed_array = np.clip(raw_seed, solver_lower, solver_upper)

        # Nearby camera-derived poses normally converge from the current joint
        # state.  Fixed alternate seeds handle the first move from home without
        # importing MoveIt sampling, scene truth, or model-generated geometry.
        midpoint = (self.lower + self.upper) / 2.0
        candidates = [
            seed_array,
            np.clip(np.asarray([0.0, -0.9, -0.25, 0.0, 1.16, 1.57]), solver_lower, solver_upper),
            midpoint,
            np.clip(seed_array + np.asarray([0.6, 0.0, 0.0, 0.0, 0.0, 0.0]), solver_lower, solver_upper),
            np.clip(seed_array - np.asarray([0.6, 0.0, 0.0, 0.0, 0.0, 0.0]), solver_lower, solver_upper),
        ]

        def residual(values: np.ndarray) -> np.ndarray:
            actual = self.forward(values)
            position = (actual[:3, 3] - target[:3, 3]) / 0.002
            orientation = Rotation.from_matrix(
                target[:3, :3].T @ actual[:3, :3]).as_rotvec() / 0.02
            return np.concatenate((position, orientation))

        attempts = []
        for initial in candidates:
            answer = least_squares(
                residual,
                initial,
                bounds=(solver_lower, solver_upper),
                max_nfev=500,
                ftol=1e-11,
                xtol=1e-11,
                gtol=1e-11,
            )
            transform = self.forward(answer.x)
            position_error, rotation_error = self.pose_error(transform, target)
            attempts.append({
                "success": bool(answer.success),
                "status": int(answer.status),
                "cost": float(answer.cost),
                "function_evaluations": int(answer.nfev),
                "position_error_m": position_error,
                "orientation_error_rad": rotation_error,
                "joints_rad": [float(value) for value in answer.x],
                "seed_distance_rad": float(np.linalg.norm(answer.x - seed_array)),
            })
        valid = [row for row in attempts
                 if row["position_error_m"] <= 0.004
                 and row["orientation_error_rad"] <= 0.05]
        chosen = min(valid, key=lambda row: (row["seed_distance_rad"], row["cost"])) if valid else min(
            attempts, key=lambda row: row["cost"])
        return {
            "success": bool(valid),
            "solver": "scipy_bounded_least_squares_from_ros2_control_urdf",
            "collision_planning_used": False,
            "moveit_used": False,
            "target_position_xyz_m": [float(value) for value in position_xyz],
            "target_quaternion_xyzw": [float(value) for value in quaternion_xyzw],
            "solution_joints_rad": chosen["joints_rad"],
            "position_error_m": chosen["position_error_m"],
            "orientation_error_rad": chosen["orientation_error_rad"],
            "attempt_count": len(attempts),
            "attempts": attempts,
            "joint_lower_rad": [float(value) for value in self.lower],
            "joint_upper_rad": [float(value) for value in self.upper],
            "joint_limit_source": self.joint_limit_source,
            "raw_seed_joints_rad": [float(value) for value in raw_seed],
            "normalized_seed_joints_rad": [float(value) for value in seed_array],
            "continuous_seed_normalization_indices": [],
        }

    def validate_joint_target(self, target: list[float] | np.ndarray) -> dict:
        values = np.asarray(target, dtype=float)
        within = bool(values.shape == (6,)
                      and np.all(values >= self.lower)
                      and np.all(values <= self.upper))
        return {
            "valid": within,
            "target_joints_rad": [float(value) for value in values],
            "joint_lower_rad": [float(value) for value in self.lower],
            "joint_upper_rad": [float(value) for value in self.upper],
            "joint_limit_source": self.joint_limit_source,
            "moveit_used": False,
        }
