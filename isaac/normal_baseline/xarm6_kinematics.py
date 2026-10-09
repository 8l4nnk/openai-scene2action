"""Numerical IK built from the loaded USD joint frames, not Franka parameters."""
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def frame(position, quaternion):
    out = np.eye(4)
    out[:3, 3] = position
    out[:3, :3] = Rotation.from_quat([*quaternion.GetImaginary(), quaternion.GetReal()]).as_matrix()
    return out


class XArmKinematics:
    def __init__(self, stage, robot_path='/World/XArm6'):
        from pxr import UsdGeom, UsdPhysics
        self.joints = []
        self.limits = []
        for name in [f'joint{i}' for i in range(1, 7)]:
            prim = next(p for p in stage.Traverse() if p.GetName() == name and p.IsA(UsdPhysics.RevoluteJoint))
            j = UsdPhysics.RevoluteJoint(prim)
            before = frame(j.GetLocalPos0Attr().Get(), j.GetLocalRot0Attr().Get())
            after = np.linalg.inv(frame(j.GetLocalPos1Attr().Get(), j.GetLocalRot1Attr().Get()))
            axis = np.eye(3)['XYZ'.index(j.GetAxisAttr().Get())]
            self.joints.append((before, axis, after))
            self.limits.append(np.deg2rad([j.GetLowerLimitAttr().Get(), j.GetUpperLimitAttr().Get()]))
        cache = UsdGeom.XformCache()
        def transform(path):
            return np.array(cache.GetLocalToWorldTransform(stage.GetPrimAtPath(robot_path+path))).T
        self.base = transform('/world')
        self.tool = np.linalg.inv(transform('/link6')) @ transform('/gripper/xarm_gripper_base_link/link_tcp')
        self.limits = np.array(self.limits)

    def forward(self, q):
        t = self.base.copy()
        for value, (before, axis, after) in zip(q, self.joints):
            r = np.eye(4)
            r[:3, :3] = Rotation.from_rotvec(axis*value).as_matrix()
            t = t @ before @ r @ after
        return t @ self.tool

    def solve(self, position, orientation, seed):
        def residual(q):
            actual = self.forward(q)
            return np.r_[actual[:3, 3]-position,
                         .2*Rotation.from_matrix(orientation.T @ actual[:3, :3]).as_rotvec()]
        candidates = [np.asarray(seed), np.deg2rad([0,30,-80,0,50,0]), np.deg2rad([-20,0,-90,0,90,0])]
        best = None
        for guess in candidates:
            sol = least_squares(residual, np.clip(guess,self.limits[:,0]+1e-6,self.limits[:,1]-1e-6),
                                bounds=(self.limits[:,0],self.limits[:,1]), max_nfev=300,
                                ftol=1e-10,xtol=1e-10,gtol=1e-10)
            score = np.linalg.norm(residual(sol.x))
            if best is None or score < best[0]:
                best = (score, sol.x)
            if score < 1e-6:
                break
        if best[0] > 1e-4:
            raise RuntimeError(f'IK failed, residual={best[0]} target={position}')
        return best[1]
