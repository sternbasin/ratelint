"""AST-based checks for missing rate limiting.

Two rules live here so far:

RL001 - a loop makes an HTTP-ish call but nothing in the loop body ever
        sleeps or backs off, so a long list of inputs turns into a burst
        of requests as fast as the interpreter can issue them.
RL002 - a web framework route handler has no decorator that looks like a
        rate limiter attached to it.

Both are heuristics based on names, not types, since there is no import
resolution here. They are meant to flag things worth a human look, not
to be a proof of correctness.
"""

import ast
from dataclasses import dataclass, field

HTTP_METHOD_NAMES = frozenset({"get", "post", "put", "patch", "delete", "head", "request"})
HTTP_FUNC_NAMES = frozenset({"urlopen"})
SLEEP_NAMES = frozenset({"sleep"})
ROUTE_METHOD_NAMES = frozenset({"route", "get", "post", "put", "patch", "delete"})

LOOP_TYPES = (ast.For, ast.AsyncFor, ast.While)
SCOPE_BOUNDARY_TYPES = LOOP_TYPES + (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class RuleConfig:
    """Name lists the checks match against. A project with an internal
    HTTP wrapper or routing decorator can extend these (see config.py)
    instead of only matching requests/flask-shaped code."""

    http_method_names: frozenset = field(default_factory=lambda: HTTP_METHOD_NAMES)
    http_func_names: frozenset = field(default_factory=lambda: HTTP_FUNC_NAMES)
    sleep_names: frozenset = field(default_factory=lambda: SLEEP_NAMES)
    route_method_names: frozenset = field(default_factory=lambda: ROUTE_METHOD_NAMES)


DEFAULT_CONFIG = RuleConfig()


@dataclass
class Finding:
    line: int
    col: int
    code: str
    message: str


def _dotted_name(node):
    """Best-effort dotted name for a Name/Attribute chain, e.g. 'requests.get'."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _is_http_call(call, config):
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in config.http_method_names:
        return True
    if isinstance(func, ast.Name) and func.id in config.http_func_names:
        return True
    return False


def _is_sleep_call(call, config):
    if not isinstance(call, ast.Call):
        return False
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in config.sleep_names:
        return True
    if isinstance(func, ast.Name) and func.id in config.sleep_names:
        return True
    return False


def _own_calls(node):
    """Yield Call nodes that belong to this loop directly, not to a loop or
    function nested inside it (those get checked on their own)."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Call):
            yield child
        if isinstance(child, SCOPE_BOUNDARY_TYPES):
            continue
        yield from _own_calls(child)


def _has_sleep_anywhere(node, config):
    """A sleep nested deeper (even inside an inner loop) still counts as
    pacing for the outer loop, so this one does not stop at boundaries."""
    for child in ast.walk(node):
        if _is_sleep_call(child, config):
            return True
    return False


def _check_loops(tree, config):
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, LOOP_TYPES):
            continue
        if _has_sleep_anywhere(node, config):
            continue
        for call in _own_calls(node):
            if _is_http_call(call, config):
                findings.append(
                    Finding(
                        line=call.lineno,
                        col=call.col_offset,
                        code="RL001",
                        message=(
                            "network call inside a loop with no sleep/backoff "
                            "anywhere in it"
                        ),
                    )
                )
    return findings


def _decorator_dotted_name(dec):
    return _dotted_name(dec.func if isinstance(dec, ast.Call) else dec)


def _looks_like_route(name, config):
    if not name:
        return False
    last = name.rsplit(".", 1)[-1]
    return last in config.route_method_names and "limit" not in name.lower()


def _looks_like_limiter(name):
    return "limit" in name.lower() if name else False


def _check_routes(tree, config):
    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = [_decorator_dotted_name(d) for d in node.decorator_list]
        if not any(_looks_like_route(n, config) for n in names):
            continue
        if any(_looks_like_limiter(n) for n in names):
            continue
        findings.append(
            Finding(
                line=node.lineno,
                col=node.col_offset,
                code="RL002",
                message=(
                    f"route handler '{node.name}' has no rate limit decorator"
                ),
            )
        )
    return findings


def check_source(source, filename="<string>", config=None):
    """Parse source and return a list of Finding, sorted by line number.

    `config` lets a caller extend the built-in name lists (see
    RuleConfig / config.load_config); the default matches only the
    common requests/flask/django-ish spellings.
    """
    config = config or DEFAULT_CONFIG
    tree = ast.parse(source, filename=filename)
    findings = _check_loops(tree, config) + _check_routes(tree, config)
    findings.sort(key=lambda f: (f.line, f.col))
    return findings
