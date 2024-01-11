import os
import typing as t


def string(key: str, default: t.Optional[str] = None) -> str:
    val = os.environ.get(key)
    if not val:
        if default is None:
            raise ValueError(f"Missing required environment variable: {key}")
        return default
    return val
