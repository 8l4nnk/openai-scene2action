from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class Point(StrictModel):
    x: float
    y: float


class Action(StrictModel):
    object_id: str = Field(min_length=1, max_length=64)
    target_id: str = Field(min_length=1, max_length=64)


class Candidate(StrictModel):
    actions: Annotated[list[Action], Field(min_length=1, max_length=16)]


class EvaluateRequest(StrictModel):
    mode: Literal['TEXT', 'IMAGE', 'IMAGE_TEXT'] = 'TEXT'
    text: str = Field(default='', max_length=4000)
    provider: Literal['replay', 'openai'] = 'replay'
    scenario: Literal['normal', 'wrong_target', 'wrong_order', 'unknown_object', 'adapter_mismatch'] = 'normal'


class Contract(StrictModel):
    id: str
    title: str
    version: str
    system_prompt: str
    steps: list[Action]
    objects: dict[str, Point]
    targets: dict[str, Point]


class ResetRequest(StrictModel):
    contract_id: Literal['sort', 'kit']


class DisturbRequest(StrictModel):
    kind: Literal['obstacle', 'sensor_loss', 'sensor_restore']
