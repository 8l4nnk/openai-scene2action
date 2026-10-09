from pathlib import Path

from .models import Contract


def load_contracts() -> dict[str, Contract]:
    root = Path(__file__).resolve().parent.parent / 'contracts'
    result = {}
    for path in sorted(root.glob('*.json')):
        contract = Contract.model_validate_json(path.read_text(encoding='utf-8'))
        if contract.id in result or not contract.steps:
            raise ValueError('Invalid contract registry')
        seen = set()
        for action in contract.steps:
            if action.object_id not in contract.objects or action.target_id not in contract.targets:
                raise ValueError('Contract refers to missing scene entity')
            if action.object_id in seen:
                raise ValueError('Repeated object unsupported by this simulator')
            seen.add(action.object_id)
        for point in [*contract.objects.values(), *contract.targets.values()]:
            if not (0.08 <= point.x <= 0.92 and 0.08 <= point.y <= 0.92):
                raise ValueError('Contract position outside simulator workspace')
        result[contract.id] = contract
    if not result:
        raise ValueError('No contracts found')
    return result
