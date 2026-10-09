"""Offline synthetic evaluation benchmark; never a safety accuracy benchmark."""
import argparse
import json
import math
import time
import uuid
from pathlib import Path

from .engine import Engine
from .models import EvaluateRequest


def benchmark(samples):
    output = []
    path = Path('.data/benchmarks') / f'{uuid.uuid4().hex}.sqlite'
    engine = Engine(path)
    try:
        for contract_id in ('sort', 'kit'):
            for mode in ('TEXT', 'IMAGE', 'IMAGE_TEXT'):
                timings = []
                for _ in range(samples):
                    engine.reset(contract_id)
                    start = time.perf_counter()
                    run = engine.evaluate(EvaluateRequest(mode=mode, text='' if mode == 'IMAGE' else '정상 작업'))
                    timings.append((time.perf_counter()-start)*1000)
                    if run['status'] != 'READY':
                        raise RuntimeError('Benchmark evaluation failed')
                timings.sort()
                quantile = lambda q: round(timings[max(0, math.ceil(len(timings)*q)-1)], 3)
                output.append(dict(contract=contract_id, mode=mode, samples=samples,
                                   p50_ms=quantile(.5), p95_ms=quantile(.95), p99_ms=quantile(.99),
                                   observed_max_ms=round(timings[-1], 3)))
    finally:
        engine.close()
    return dict(provider='synthetic-replay-v1', scope='Full Engine.evaluate call including SQLite write; excludes HTTP, live model, robot control and stopping.', results=output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000:
        parser.error('samples must be between 1 and 1000')
    print(json.dumps(benchmark(args.samples), indent=2))
