"""Offline 2D geometry comparison including validation and ctypes marshalling."""
import argparse
import json
import math
import time

from .geometry import PythonGeometry, configured_geometry


def measure(geometry,commands,world,samples):
    for _ in range(10):
        if not geometry.path_clear(commands,world):
            raise RuntimeError('Benchmark fixture unexpectedly blocked')
    times=[]
    for _ in range(samples):
        started=time.perf_counter_ns()
        clear=geometry.path_clear(commands,world)
        elapsed=time.perf_counter_ns()-started
        if not clear:
            raise RuntimeError('Benchmark fixture unexpectedly blocked')
        times.append(elapsed/1000)
    times.sort()
    return {f'p{q}_us':round(times[math.ceil(samples*q/100)-1],3) for q in (50,95,99)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples',type=int,default=200)
    args=parser.parse_args()
    if not 1<=args.samples<=2000:
        parser.error('samples must be 1..2000')
    native=configured_geometry()
    if native.name!='native':
        parser.error('Set S2A_GEOMETRY_BACKEND=native; explicit compiled backend required')
    results=[]
    for count,obstacles in ((8,0),(16,128),(64,512)):
        commands=[{'position':[.9 if i%2==0 else .1,.2]} for i in range(count)]
        world={'position':[.1,.2],'obstacles':[[.4,.6,.6,.8] for _ in range(obstacles)]}
        python_result=measure(PythonGeometry(),commands,world,args.samples)
        native_result=measure(native,commands,world,args.samples)
        results.append(dict(commands=count,obstacles=obstacles,samples=args.samples,
                            python=python_result,native=native_result,
                            p50_speedup=round(python_result['p50_us']/native_result['p50_us'],3)))
    print(json.dumps(dict(scope='Valid clear-path synthetic 2D fixtures; includes validation and Python/native marshalling. No models, HTTP, database, Isaac or robot stopping. Both backends receive identical inputs. Not a real-time bound.',results=results),indent=2))


if __name__=='__main__':
    main()
