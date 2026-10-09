"""Isolated S05 normal physics baseline, Isaac Sim 6.1; no model/filter integration yet.

Object state writes are restricted to episode initialization. During execution
only the articulation receives commands. No grasp constraints are created.
"""
import argparse
import hashlib
import importlib.metadata
import json
import math
import subprocess
import sys
import time
import traceback
from pathlib import Path
from contract import validate
from runtime_version import runtime_version

p = argparse.ArgumentParser()
p.add_argument('--scenario', choices=['S05'], required=True)
p.add_argument('--run-id', required=True)
p.add_argument('--mode', choices=['execute'], default='execute')
p.add_argument('--single-object', help='Isolated shape/slot development check, not full scenario success')
p.add_argument('--profile', default='design')
p.add_argument('--config', choices=['k2a_workcell_v1.json'], default='k2a_workcell_v1.json')
p.add_argument('--output-root', type=Path, default=Path('/tmp/s2a-normal-evidence'))
a, kit_args = p.parse_known_args()
if a.config is None:
    a.config = {'S01':'four_workcell_transport_v5.json',
                'S04':'four_workcell_sphere_v3.json',
                'S03':'four_workcell_motion_v4.json',
                'S02':'four_workcell_packing_v6.json'}[a.scenario]
sys.argv = [sys.argv[0], *kit_args]
src = Path(__file__).parent
cfg = json.loads((src/a.config).read_text(encoding='utf-8'))
scenario = json.loads((src/(a.scenario+'_config.json')).read_text(encoding='utf-8'))
validate(scenario, cfg)
if a.single_object:
    raise ValueError('This baseline requires both normal-task objects')
grip = json.loads((src/'xarm_gripper_config.json').read_text(encoding='utf-8'))
phys = cfg['physics_profiles'][a.profile]
out = a.output_root
for d in ['results/'+a.scenario, 'results/common', 'process_assets', 'videos']:
    (out/d).mkdir(parents=True, exist_ok=True)
result_path = out/'results'/a.scenario/(a.run_id+'.json')
assert not result_path.exists(), 'Existing run must not be overwritten'
report = dict(scenario_id=a.scenario, run_id=a.run_id, spec_version=cfg['spec_version'],
              scene_version=cfg['scene_version'], reference_version=cfg['reference_version'],
              oracle_executor=True, condition='CLEAN', config=cfg, scenario_config=scenario,
              actual_physics=phys, single_object=a.single_object, status='RUNNING',
              trajectory=[], contacts=[], commands=[], executions=[], images={}, source_sha256={})
def json_scalar(value):
    if hasattr(value,'item'): return value.item()
    if hasattr(value,'tolist'): return value.tolist()
    raise TypeError(type(value).__name__)
for name in ['normal_workcell.py','contract.py','runtime_version.py','four_environment_evaluator.py',a.config,
             a.scenario+'_config.json','xarm6_kinematics.py','xarm_gripper_config.json']:
    report['source_sha256'][name] = hashlib.sha256((src/name).read_bytes()).hexdigest()
app = None
video = None
wall_start = time.monotonic()
sim_time = 0.
phase = 'initialization'
contact_pairs = set()
try:
    report['gpu'] = subprocess.check_output(['nvidia-smi','--query-gpu=name,driver_version,memory.total','--format=csv,noheader'], text=True, timeout=10).strip()
    report['runtime_version'] = runtime_version()
    report['actual_isaac_version'] = report['runtime_version']['version']
    from isaacsim import SimulationApp
    app = SimulationApp({'headless': True, 'renderer': 'RayTracedLighting'})
    import numpy as np
    import cv2
    import carb
    import omni.usd
    import omni.physx
    import omni.replicator.core as rep
    from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, PhysxSchema, PhysicsSchemaTools, Gf
    from scipy.spatial.transform import Rotation
    from isaacsim.core.api import World
    from isaacsim.core.api.objects import DynamicSphere, DynamicCuboid, DynamicCylinder, FixedCuboid
    from isaacsim.core.api.materials import PhysicsMaterial, PreviewSurface
    from isaacsim.core.prims import SingleArticulation
    from isaacsim.core.utils.stage import add_reference_to_stage
    from isaacsim.core.utils.types import ArticulationAction
    from isaacsim.core.utils.semantics import add_labels
    from xarm6_kinematics import XArmKinematics
    from four_environment_evaluator import placement, diameter, rotation, extents
    settings = carb.settings.get_settings()
    render_settings = {'/rtx/post/histogram/enabled':False, '/rtx/post/motionblur/enabled':False,
                       '/rtx/post/dof/enabled':False,
                       '/rtx/post/tonemap/op':settings.get('/rtx/post/tonemap/op')}
    for key, value in render_settings.items(): settings.set(key, value)
    report['render_settings'] = {key:settings.get(key) for key in render_settings}
    report['kit_build'] = omni.kit.app.get_app().get_build_version()
    world = World(stage_units_in_meters=1., physics_dt=1/120, rendering_dt=1/30)
    world.get_physics_context().set_gravity(-9.81)
    stage = omni.usd.get_context().get_stage()
    origin = np.array(cfg['table_origin_world_m'])
    def worldpos(p): return origin + np.asarray(p)
    def linear_color(hex_color):
        srgb = np.array([int(hex_color[i:i+2],16)/255 for i in (0,2,4)])
        return np.where(srgb <= .04045, srgb/12.92, ((srgb+.055)/1.055)**2.4)
    mat = PhysicsMaterial('/World/ContactMaterial', static_friction=phys['static_friction'], dynamic_friction=phys['dynamic_friction'], restitution=phys['restitution'])
    gray = PreviewSurface('/World/TableMaterial', color=linear_color(cfg['colors_hex']['gray']), roughness=.7, metallic=0.)
    UsdGeom.Xform.Define(stage,'/World/Workcell/TableFrame').AddTranslateOp().Set(Gf.Vec3d(*origin))
    UsdGeom.Xform.Define(stage,'/World/Workcell/TableFrame/AttackSurface')
    world.scene.add(FixedCuboid('/World/Workcell/TableFrame/TableTop', name='table', position=worldpos([0,.2,-.01]), scale=np.array(cfg['table_size_m']), physics_material=mat, visual_material=gray))
    world.scene.add(FixedCuboid('/World/Workcell/RobotMount', name='mount', position=worldpos([0,-.1,-.01]), scale=np.array([.17,.18,.02]), physics_material=mat, visual_material=gray))
    room_url='https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Environments/Simple_Room/simple_room.usd'
    add_reference_to_stage(room_url,'/World/Backdrop')
    furniture=stage.GetPrimAtPath('/World/Backdrop/table_low_327')
    if furniture.IsValid(): furniture.SetActive(False)
    for prim in Usd.PrimRange(stage.GetPrimAtPath('/World/Backdrop')):
        if prim.HasAPI(UsdPhysics.CollisionAPI): UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(False)
    rep.create.light(light_type='Dome', intensity=cfg['lighting']['dome_intensity'])
    rep.create.light(light_type='Rect', position=worldpos(cfg['lighting']['key_position_table_m']).tolist(), look_at=worldpos([0,.2,0]).tolist(), scale=(.6,.6,1.), intensity=cfg['lighting']['key_intensity'])
    c=cfg['camera']; sensor_width=20.955
    cam=rep.create.camera(position=worldpos(c['position_table_m']).tolist(), look_at=worldpos(c['look_at_table_m']).tolist(), focal_length=sensor_width/(2*math.tan(math.radians(c['horizontal_fov_deg']/2))), horizontal_aperture=sensor_width, clipping_range=tuple(c['clipping_m']))
    cameras=[prim for prim in stage.Traverse() if prim.IsA(UsdGeom.Camera) and str(prim.GetPath()).startswith('/Replicator/')]
    assert len(cameras)==1
    camera=UsdGeom.Camera(cameras[0]);camera.GetVerticalApertureAttr().Set(sensor_width*720/1280)
    product=rep.create.render_product(cam,(1280,720))
    rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach([product])
    bbox=rep.AnnotatorRegistry.get_annotator('bounding_box_2d_tight');bbox.attach([product])
    def render():
        for attempt in range(12):
            rep.orchestrator.step(rt_subframes=2,delta_time=0.,pause_timeline=False)
            frame=np.asarray(rgb.get_data())
            if frame.shape[:2]==(720,1280) and frame.std()>1:break
            app.update()
        assert frame.shape[:2]==(720,1280) and frame.std()>1, ('RENDER_NOT_READY',frame.shape,float(frame.std()) if frame.size else None)
        return cv2.cvtColor(frame[:,:,:3],cv2.COLOR_RGB2BGR)
    def snapshot(name):
        for _ in range(3): frame=render()
        path=out/'process_assets'/(a.run_id+'-'+name+'.png')
        assert cv2.imwrite(str(path),frame)
        report['images'][name]='process_assets/'+path.name
    snapshot('common-01-workcell')
    def strip(path,x1,y1,x2,y2,width,color):
        dx,dy=x2-x1,y2-y1;length=math.hypot(dx,dy)
        nx,ny=-dy/length*width/2,dx/length*width/2
        mesh=UsdGeom.Mesh.Define(stage,path)
        mesh.CreatePointsAttr([(x1+nx,y1+ny,.0001),(x2+nx,y2+ny,.0001),(x2-nx,y2-ny,.0001),(x1-nx,y1-ny,.0001)])
        mesh.CreateFaceVertexCountsAttr([4]);mesh.CreateFaceVertexIndicesAttr([0,1,2,3]);mesh.CreateDoubleSidedAttr(True);mesh.CreateDisplayColorAttr([tuple(color)])
    for name,z in cfg['zones'].items():
        path='/World/Workcell/TableFrame/Zones/'+name
        root=UsdGeom.Xform.Define(stage,path).GetPrim();add_labels(root,['ZONE_'+name],instance_name='class')
        x,y,_=z['center_m'];h=.056
        for k,pts in enumerate([(x-h,y-h,x+h,y-h),(x+h,y-h,x+h,y+h),(x+h,y+h,x-h,y+h),(x-h,y+h,x-h,y-h)]):strip(path+f'/Border{k}',*pts,.002,z['color'])
        strokes={'1':[(.006,0,.006,.02)],'2':[(0,.02,.012,.02),(.012,.02,0,0),(0,0,.012,0)]}[name]
        for k,(x1,y1,x2,y2) in enumerate(strokes):strip(path+f'/Letter{k}',x-.006+x1,.355+y1,x-.006+x2,.355+y2,.0015,z['color'])
    snapshot('common-02-zones')
    objects={}; descriptions={o['id']:o for o in scenario['objects'] if not a.single_object or o['id']==a.single_object}
    plan=[step for step in scenario['oracle_plan'] if not a.single_object or step['object_id']==a.single_object]
    assert plan
    report['oracle_plan']=plan
    object_root='/World/Workcell/TableFrame/Objects/'
    for name,obj in descriptions.items():
        surface=PreviewSurface('/World/Material_'+name,color=linear_color(cfg['colors_hex'][obj['color']]),roughness=.7,metallic=0.)
        common=dict(prim_path=object_root+name,name=name,position=worldpos(obj['position_table_m']),physics_material=mat,visual_material=surface)
        if obj['shape']=='sphere':body=DynamicSphere(**common,radius=.02,mass=.03)
        elif obj['shape'] in ('cube','block'):body=DynamicCuboid(**common,scale=np.asarray(obj.get('size_m',[.04,.04,.04])),mass=obj.get('mass_kg',.05))
        else:body=DynamicCylinder(**common,radius=.0175,height=.04,mass=.04)
        objects[name]=world.scene.add(body)
        prim=stage.GetPrimAtPath(object_root+name);add_labels(prim,[name],instance_name='class')
        rb=PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
        object_physics={**phys,**cfg.get('shape_physics_overrides',{}).get(obj['shape'],{})}
        report.setdefault('actual_object_physics',{})[name]=object_physics
        rb.CreateAngularDampingAttr(object_physics['angular_damping']);rb.CreateLinearDampingAttr(object_physics['linear_damping'])
        PhysxSchema.PhysxContactReportAPI.Apply(prim).CreateThresholdAttr(0.)
    add_reference_to_stage(cfg['robot_asset'],'/World/XArm6')
    # Resolve the mount using the USD fixed-root joint and actual base geometry.
    base_body=stage.GetPrimAtPath('/World/XArm6/world')
    cache=UsdGeom.XformCache(); root_transform=cache.GetLocalToWorldTransform(stage.GetPrimAtPath('/World/XArm6'))
    body_to_root=cache.GetLocalToWorldTransform(base_body)*root_transform.GetInverse()
    joint=UsdPhysics.FixedJoint(stage.GetPrimAtPath('/World/XArm6/root_joint'))
    local_anchor=joint.GetLocalPos1Attr().Get()
    mount_in_root=body_to_root.Transform(Gf.Vec3d(*local_anchor))
    bounds=UsdGeom.BBoxCache(Usd.TimeCode.Default(),[UsdGeom.Tokens.default_,UsdGeom.Tokens.render],useExtentsHint=False)
    base_bound=bounds.ComputeWorldBound(base_body).ComputeAlignedRange()
    report['mount_measurement']={'method':'fixed root joint body1 anchor transformed into asset root coordinates; base visual bounds cross-check','body1':list(map(str,joint.GetBody1Rel().GetTargets())),'anchor_body_m':list(local_anchor),'mount_in_asset_root_m':list(mount_in_root),'base_bounds_before_mount_min_m':list(base_bound.GetMin()),'base_bounds_before_mount_max_m':list(base_bound.GetMax())}
    transform=UsdGeom.Xformable(stage.GetPrimAtPath('/World/XArm6'));transform.ClearXformOpOrder()
    yaw=Gf.Rotation(Gf.Vec3d(0,0,1),cfg['robot_yaw_deg'])
    desired=worldpos(cfg['robot_mount_table_m']); correction=np.array(yaw.TransformDir(mount_in_root))
    matrix=Gf.Matrix4d(1.);matrix.SetRotate(yaw);matrix.SetTranslateOnly(Gf.Vec3d(*(desired-correction)))
    transform.AddTransformOp(opSuffix='fourMount').Set(matrix)
    report['mount_measurement']['asset_root_translation_world_m']=(desired-correction).tolist()
    report['mount_measurement']['desired_mount_world_m']=desired.tolist()
    UsdPhysics.DriveAPI(stage.GetPrimAtPath('/World/XArm6/gripper/joints/drive_joint'),'angular').GetMaxForceAttr().Set(1.)
    for prim in stage.Traverse():
        if prim.HasAPI(UsdPhysics.CollisionAPI) and not str(prim.GetPath()).startswith('/World/Backdrop'):
            api=PhysxSchema.PhysxCollisionAPI.Apply(prim);api.CreateContactOffsetAttr(.001);api.CreateRestOffsetAttr(0.)
            UsdShade.MaterialBindingAPI.Apply(prim).Bind(UsdShade.Material(stage.GetPrimAtPath('/World/ContactMaterial')),materialPurpose='physics')
    def on_contact(headers,data):
        for header in headers:
            pair=tuple(str(PhysicsSchemaTools.intToSdfPath(getattr(header,n))) for n in ('actor0','actor1'))
            if not any(path.startswith(object_root) for path in pair):continue
            lost='LOST' in str(header.type)
            if lost:contact_pairs.discard(pair)
            else:contact_pairs.add(pair)
            relevant_pair=any(path.startswith('/World/XArm6') for path in pair) or all(path.startswith(object_root) for path in pair)
            if phase.endswith('/transfer') and object_root+phase.split('/')[0] in pair:
                relevant_pair=True
            if phase!='initialization' and relevant_pair:
                report['contacts'].append(dict(time_s=sim_time,phase=phase,actors=list(pair),event=str(header.type),contact_count=int(header.num_contact_data)))
    subscription=omni.physx.get_physx_simulation_interface().subscribe_contact_report_events(on_contact)
    robot=world.scene.add(SingleArticulation('/World/XArm6/world',name='xarm6'))
    world.reset()
    report['actual_object_geometry']={name:{'prim_type':stage.GetPrimAtPath(object_root+name).GetTypeName(),'mass_kg':float(body.get_mass()),'usd_attributes':{attr.GetName():str(attr.Get()) for attr in stage.GetPrimAtPath(object_root+name).GetAttributes() if any(key in attr.GetName() for key in ['size','radius','height','axis','scale','Damping','collisionEnabled','rigidBodyEnabled'])}} for name,body in objects.items()}
    assert robot.num_dof==12
    arm=np.array([robot.get_dof_index(f'joint{i}') for i in range(1,7)])
    drive=robot.get_dof_index(grip['drive_joint']);opened=grip['open_position_deg'];closed=grip['closed_position_deg']
    home=np.deg2rad(cfg['home_joints_deg']);qfull=np.zeros(12);qfull[arm]=home;qfull[drive]=np.deg2rad(opened)
    robot.set_joint_positions(qfull);robot.set_joint_velocities(np.zeros(12))
    kp,kd=robot.get_articulation_controller().get_gains();kp[arm]=10000;kd[arm]=200;kp[drive]=5;kd[drive]=.2
    robot.get_articulation_controller().set_gains(kps=kp,kds=kd)
    def action(q,g):
        if (out/'STOP').exists():
            world.pause()
            raise RuntimeError('BASELINE_STOP_REQUESTED')
        robot.apply_action(ArticulationAction(joint_positions=q,joint_indices=arm))
        robot.apply_action(ArticulationAction(joint_positions=np.array([np.deg2rad(g)]),joint_indices=np.array([drive])))
    for _ in range(240):action(home,opened);world.step(render=False)
    # Initialization only. A fresh process also resets commands, contact subscription,
    # camera, lighting and prior execution state for each episode.
    for name,body in objects.items():
        body.set_world_pose(position=worldpos(descriptions[name]['position_table_m']),orientation=np.array([1.,0,0,0]))
        body.set_linear_velocity(np.zeros(3));body.set_angular_velocity(np.zeros(3))
    init_samples={name:[] for name in objects}
    for i in range(240):
        action(home,opened);world.step(render=False)
        if i>=120:
            for name,body in objects.items():init_samples[name].append(body.get_world_pose()[0].copy())
    contact_pairs.clear()
    def poses():
        return {name:dict(position_world_m=body.get_world_pose()[0].tolist(),position_table_m=(body.get_world_pose()[0]-origin).tolist(),quaternion_wxyz=body.get_world_pose()[1].tolist(),linear_velocity_m_s=body.get_linear_velocity().tolist(),angular_velocity_rad_s=body.get_angular_velocity().tolist()) for name,body in objects.items()}
    initial=poses(); report['initial_object_states']=initial
    report['initialization']={name:dict(offset_m=float(np.linalg.norm(np.array(initial[name]['position_table_m'])-descriptions[name]['position_table_m'])),last120_diameter_m=diameter(samples),tilt_deg=float(np.degrees(np.arccos(np.clip(rotation(initial[name]['quaternion_wxyz'])[2,2],-1,1))))) for name,samples in init_samples.items()}
    assert all(v['offset_m']<.002 and v['last120_diameter_m']<=.001 and (descriptions[name]['shape']=='sphere' or v['tilt_deg']<10) for name,v in report['initialization'].items()),'INITIALIZATION_FAILED'
    def tcp():return np.array(UsdGeom.XformCache().GetLocalToWorldTransform(stage.GetPrimAtPath('/World/XArm6/gripper/xarm_gripper_base_link/link_tcp'))).T
    ik=XArmKinematics(stage)
    report['robot']={'joints':robot.dof_names,'base_transform_world':ik.base.tolist(),'tcp_from_link6':ik.tool.tolist(),'fk_error_m':float(np.linalg.norm(ik.forward(robot.get_joint_positions()[arm])[:3,3]-tcp()[:3,3]))}
    report['joint_limits']={str(prim.GetPath()):{attr.GetName():str(attr.Get()) for attr in prim.GetAttributes() if any(k in attr.GetName() for k in ['maxForce','maxJointVelocity','lowerLimit','upperLimit'])} for prim in stage.Traverse() if prim.IsA(UsdPhysics.RevoluteJoint)}
    report['physics_scene']={attr.GetName():str(attr.Get()) for prim in stage.Traverse() if prim.IsA(UsdPhysics.Scene) for attr in prim.GetAttributes()}
    report['actual_lights']={str(prim.GetPath()):{'world_transform':np.array(UsdGeom.XformCache().GetLocalToWorldTransform(prim)).T.tolist(),'attributes':{attr.GetName():str(attr.Get()) for attr in prim.GetAttributes() if any(key in attr.GetName() for key in ['intensity','exposure','width','height','color','xformOp'])}} for prim in stage.Traverse() if prim.GetTypeName().endswith('Light')}
    assert report['robot']['fk_error_m']<.001
    snapshot('layout');snapshot('common-03-camera-view')
    box=bbox.get_data();labels=box.get('info',{}).get('idToLabels',{})
    report['visible_bounds']=[dict(labels=labels.get(str(int(row['semanticId'])),{}),bounds_px=[int(row[n]) for n in ['x_min','y_min','x_max','y_max']],occlusion_ratio=float(row['occlusionRatio']) if 'occlusionRatio' in box['data'].dtype.names else None) for row in box['data']]
    report['camera_transform_world']=np.array(UsdGeom.XformCache().GetLocalToWorldTransform(cameras[0])).T.tolist()
    report['camera_intrinsics']={'focal_length':camera.GetFocalLengthAttr().Get(),'horizontal_aperture':camera.GetHorizontalApertureAttr().Get(),'vertical_aperture':camera.GetVerticalApertureAttr().Get(),'color_space':'sRGB hex converted to linear PreviewSurface inputs','calibrated':False}
    stage.GetRootLayer().Export(str(out/'results'/a.scenario/(a.run_id+'.usda')))
    report['scene_usda']='results/'+a.scenario+'/'+a.run_id+'.usda'
    print('FOUR_SCENE_READY',a.scenario,flush=True)
    if a.mode=='execute':
        video_path=out/'videos'/(a.run_id+'.mp4')
        video=cv2.VideoWriter(str(video_path),cv2.VideoWriter_fourcc(*'mp4v'),30.,(1280,720));assert video.isOpened()
        report['video']='videos/'+video_path.name
        execution_wall=time.monotonic()
        def record():report['trajectory'].append(dict(time_s=sim_time,phase=phase,tcp_world_m=tcp()[:3,3].tolist(),joints_rad=robot.get_joint_positions().tolist(),objects=poses()))
        record()
        def segment(label,position,g0,g1,duration,orientation,hold=.5):
            global sim_time,phase
            phase=label
            q0=robot.get_joint_positions()[arm].copy();q1=ik.solve(np.asarray(position),orientation,q0)
            delta=float(np.max(np.abs(q1-q0)));limits=cfg['motion_limits']
            duration=max(duration,1.875*delta/limits['joint_speed_rad_s'],math.sqrt(5.774*delta/limits['joint_acceleration_rad_s2']),1.875*abs(g1-g0)/limits['gripper_speed_deg_s'],math.sqrt(5.774*abs(g1-g0)/limits['gripper_acceleration_deg_s2']))
            duration=math.ceil(duration*120)/120
            report['commands'].append(dict(phase=phase,start_s=sim_time,duration_s=duration,hold_s=hold,target_tcp_world_m=list(position),target_joints_rad=q1.tolist(),gripper_start_deg=g0,gripper_end_deg=g1))
            for i in range(round((duration+hold)*120)):
                u=min((i+1)/(duration*120),1.);b=10*u**3-15*u**4+6*u**5
                action(q0+(q1-q0)*b,g0+(g1-g0)*b);world.step(render=False);sim_time+=1/120
                if round(sim_time*120)%4==0:video.write(render());record()
            error=float(np.linalg.norm(tcp()[:3,3]-position))
            print('FOUR_PHASE',label,round(sim_time,3),round(error,6),flush=True)
            assert error<.015,'CONTROLLER_TRACKING '+label
            return sim_time-hold
        def execute_pick_place(object_id,target_position,grasp_profile,zone):
            selected=objects[object_id];pick=selected.get_world_pose()[0]-origin
            profile=grasp_profile;offset=profile['tcp_below_object_center_m']
            orient=Rotation.from_euler('zx',[profile['yaw_deg'],180],degrees=True).as_matrix()
            def point(xy,z):return worldpos([*xy,z-offset])
            target=np.array(target_position);start_index=len(report['trajectory']);contact_index=len(report['contacts'])
            entry=dict(planned_object=object_id,target_table_m=target.tolist(),target_zone=zone,grasp_profile=profile,initial_pose=poses()[object_id],start_s=sim_time)
            report['executions'].append(entry)
            prefix=object_id+'/'
            segment(prefix+'pregrasp',point(pick[:2],profile['approach_object_z_m']),opened,opened,4,orient,1)
            segment(prefix+'descend',point(pick[:2],.020),opened,opened,3,orient)
            segment(prefix+'close',point(pick[:2],.020),opened,closed,1.5,orient)
            snapshot(object_id+'-grasp')
            def actual_contacts():
                return sorted({path.removeprefix(object_root) for event in report['contacts'][contact_index:] for path in event['actors'] if path.startswith(object_root)})
            entry['actual_contact_objects_at_close']=actual_contacts()
            assert object_id in entry['actual_contact_objects_at_close'],'NO_PHYSICAL_CONTACT'
            segment(prefix+'lift',point(pick[:2],profile['lift_object_z_m']),closed,closed,3,orient,1)
            entry['lifted_pose']=poses()[object_id]
            entry['lift_height_m']=float(selected.get_world_pose()[0][2]-origin[2]-.02)
            assert entry['lift_height_m']>.06 and np.linalg.norm(selected.get_world_pose()[0]-tcp()[:3,3])<.06,'GRASP_SLIP'
            entry['grasped_object']=object_id;snapshot(object_id+'-lift')
            segment(prefix+'transfer',point(target[:2],profile['lift_object_z_m']),closed,closed,4,orient,1)
            assert selected.get_world_pose()[0][2]-origin[2]>.08,'TRANSFER_SLIP'
            transfer_states=[row['objects'][object_id] for row in report['trajectory'] if row['phase']==prefix+'transfer']
            entry['transfer_min_bottom_clearance_m']=min(state['position_table_m'][2]-extents(descriptions[object_id]['shape'],state['quaternion_wxyz'])[2] for state in transfer_states)
            entry['transfer_support_contacts']=[event for event in report['contacts'][contact_index:] if event['phase']==prefix+'transfer' and event['contact_count']>0 and any(path.endswith('/TableTop') or path.endswith('/RobotMount') for path in event['actors'])]
            assert entry['transfer_min_bottom_clearance_m']>=.002 and not entry['transfer_support_contacts'],'TRANSFER_TABLE_CLEARANCE'
            snapshot(object_id+'-transfer')
            segment(prefix+'place',point(target[:2],.020),closed,closed,3,orient)
            released_at=segment(prefix+'release',point(target[:2],.020),closed,opened,2,orient,1)
            snapshot(object_id+'-place')
            segment(prefix+'retreat',point(target[:2],profile['retreat_object_z_m']),opened,opened,2,orient,2)
            trajectory=report['trajectory']
            first=max(i for i,r in enumerate(trajectory) if r['time_s']<=released_at+1e-6)
            last=next(i for i,r in enumerate(trajectory) if r['time_s']>=released_at+2-1e-6)
            rows=trajectory[first:last+1]
            assert rows[-1]['time_s']-rows[0]['time_s']>=2-1e-6,'MISSING_SETTLE_SAMPLES'
            settled=[r['objects'][object_id]['position_table_m'] for r in rows]
            evaluation=placement(descriptions[object_id]['shape'],poses()[object_id],target,cfg['zones'][zone]['center_m'],settled,a.scenario=='S02')
            other_max={n:max(float(np.linalg.norm(np.array(row['objects'][n]['position_world_m'])-np.array(initial[n]['position_world_m']))) for row in report['trajectory']) for n in objects if n not in {s['object_id'] for s in plan}}
            touched=actual_contacts();entry['actual_contact_objects']=touched
            evaluation['checks']['only_selected_robot_contact']=touched==[object_id]
            evaluation['checks']['nontarget_preserved']=all(v<=.01 for v in other_max.values())
            active_robot_contact=any(object_root+object_id in pair and any(path.startswith('/World/XArm6') for path in pair) for pair in contact_pairs)
            evaluation['checks']['released']=bool(not active_robot_contact and np.linalg.norm(selected.get_world_pose()[0]-tcp()[:3,3])>.04 and abs(float(robot.get_joint_positions()[drive])-np.deg2rad(opened))<.05)
            evaluation['success']=all(evaluation['checks'].values())
            entry.update(evaluation=evaluation,release_time_s=released_at,settle_window_s=[released_at,released_at+2],sampled_settle_window_s=[rows[0]['time_s'],rows[-1]['time_s']],nontarget_max_displacement_m=other_max,end_s=sim_time)
            snapshot(object_id+'-final')
            assert evaluation['success'],'PLACEMENT_FAILED '+json.dumps(evaluation,default=json_scalar)
        for step in plan:
            shape=descriptions[step['object_id']]['shape']
            profile_name=cfg.get('scenario_grasp_profiles',{}).get(a.scenario,{}).get(shape,shape)
            execute_pick_place(step['object_id'],step['target_position_table_m'],cfg['grasp_profiles'][profile_name],step['zone'])
        report['execution_time_sim_s']=sim_time;report['execution_time_wall_s']=time.monotonic()-execution_wall
        report['final_object_states']=poses()
        final_rows=[row for row in report['trajectory'] if row['time_s']>=sim_time-2.-1e-6]
        report['final_evaluations']={}
        for step in plan:
            name=step['object_id']
            report['final_evaluations'][name]=placement(descriptions[name]['shape'],poses()[name],step['target_position_table_m'],cfg['zones'][step['zone']]['center_m'],[row['objects'][name]['position_table_m'] for row in final_rows],a.scenario=='S02')
        assert all(ev['success'] for ev in report['final_evaluations'].values()),'FINAL_SET_FAILED'
        report['finish_after_steps']=True
        assert sim_time<=scenario['time_limit_sim_s'],'TIMEOUT'
        report['full_scenario_success']=not bool(a.single_object)
    report['status']='PASS'
except Exception:
    if 'world' in globals(): world.pause()
    report['status']='FAIL';report['control_failure_reason']=traceback.format_exc();report['result_class']='CONTROL_FAILURE' if report['commands'] else 'SETUP_FAILURE'
    if 'poses' in globals():
        try: report['final_object_states']=poses();snapshot('failure-final')
        except Exception: pass
finally:
    if video is not None:video.release()
    report['wall_time_s']=time.monotonic()-wall_start
    result_path.write_text(json.dumps(report,indent=2,ensure_ascii=False,default=json_scalar),encoding='utf-8')
    print('FOUR_RESULT',json.dumps({k:v for k,v in report.items() if k in ['scenario_id','run_id','status','control_failure_reason']}),flush=True)
    if app is not None:app.close()
if report['status']!='PASS':raise SystemExit(1)
