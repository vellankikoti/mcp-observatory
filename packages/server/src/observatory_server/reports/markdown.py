from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def render_markdown(model: Any) -> str:
    if isinstance(model, BaseModel):
        name = type(model).__name__
        body = model.model_dump_json(indent=2)
        return f"## {name}\n\n```json\n{body}\n```\n"
    name = type(model).__name__
    body = json.dumps(model, indent=2, default=str)
    return f"## {name}\n\n```json\n{body}\n```\n"
