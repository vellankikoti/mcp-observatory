from __future__ import annotations

import re
from datetime import timedelta

_WINDOW_RE = re.compile(r"^(?P<n>\d+)(?P<unit>[smhd])$")


def _parse_window(window: str) -> timedelta:
    m = _WINDOW_RE.match(window)
    if m is None:
        raise ValueError(f"invalid window: {window}")
    n = int(m.group("n"))
    return {
        "s": timedelta(seconds=n),
        "m": timedelta(minutes=n),
        "h": timedelta(hours=n),
        "d": timedelta(days=n),
    }[m.group("unit")]
