from dataclasses import dataclass, field
from typing import Dict, List, Union

import marshmallow_dataclass


@dataclass
class Job:
    name: str
    args: List[str] = field(default_factory=list)
    kwargs: Dict[str, Union[None, int, float, str]] = field(default_factory=dict)


JobSchema = marshmallow_dataclass.class_schema(Job)
