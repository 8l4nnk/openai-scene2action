"""Fixed normal-only baseline contract, not a general robot command interface."""
import math


def validate(scenario, settings):
    expected=[('S05_sphere_red','1'),('S05_sphere_blue','2')]
    plan=scenario.get('oracle_plan',[])
    if scenario.get('scenario_id')!='S05' or [
            (s.get('object_id'),s.get('zone')) for s in plan] != expected:
        raise ValueError('Only the ordered S05 normal task is supported')
    for step in plan:
        target=step.get('target_position_table_m',[])
        zone=settings['zones'][step['zone']]['center_m']
        if len(target)!=3 or not all(type(v) in (float,int) and math.isfinite(v) for v in target):
            raise ValueError('Target must be finite SI coordinates')
        if abs(target[2]-.02)>1e-9 or any(abs(target[i]-zone[i])>1e-9 for i in (0,1)):
            raise ValueError('Target must match the trusted zone centre')
