"""Loading a JSON config file that extends the built-in name lists.

Plain JSON rather than TOML so this stays stdlib-only down to the
project's minimum Python version - tomllib isn't available before 3.11
and pulling in tomli would mean a dependency. Every key in the file is
a list of *extra* names added to the defaults, not a replacement, so a
project only has to name the things it does differently, e.g. an
internal HTTP client wrapper or a homegrown routing decorator:

    {
        "http_methods": ["fetch"],
        "route_methods": ["endpoint"]
    }
"""

import json
from dataclasses import replace
from pathlib import Path

from .checks import RuleConfig

CONFIG_KEYS = {
    "http_methods": "http_method_names",
    "http_funcs": "http_func_names",
    "sleep_names": "sleep_names",
    "route_methods": "route_method_names",
}

DEFAULT_CONFIG_FILENAMES = (".ratelint.json", "ratelint.json")


def load_config(path):
    """Read a JSON config file and return a RuleConfig with the extra
    names merged into the defaults.

    Raises ValueError (including via json.JSONDecodeError, which is a
    subclass) or OSError on a bad file; callers should report those to
    the user rather than let a typo silently do nothing.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config file must contain a JSON object")

    unknown = set(data) - set(CONFIG_KEYS)
    if unknown:
        raise ValueError(f"unknown config key(s): {', '.join(sorted(unknown))}")

    base = RuleConfig()
    updates = {}
    for json_key, field_name in CONFIG_KEYS.items():
        if json_key not in data:
            continue
        extra = data[json_key]
        if not isinstance(extra, list) or not all(isinstance(x, str) for x in extra):
            raise ValueError(f"{json_key!r} must be a list of strings")
        updates[field_name] = frozenset(getattr(base, field_name)) | frozenset(extra)

    return replace(base, **updates)


def find_default_config(directory):
    """Look for a recognized config filename in `directory`. Returns a
    Path, or None if none of them are present."""
    directory = Path(directory)
    for name in DEFAULT_CONFIG_FILENAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None
