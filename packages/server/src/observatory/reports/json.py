from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def render_json(model: Any) -> str:
    if isinstance(model, BaseModel):
        return model.model_dump_json(indent=2) + "\n"
    return json.dumps(model, indent=2, default=str) + "\n"
