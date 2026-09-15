"""Command line entry point: `python -m ratelint path [path ...]`."""

import argparse
import sys
from pathlib import Path

from .checks import check_source


def _iter_python_files(paths):
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            yield from sorted(p.rglob("*.py"))
        elif p.suffix == ".py":
            yield p
        else:
            print(f"skipping {p}: not a .py file", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="ratelint",
        description="Flag likely rate-limiting mistakes in Python code.",
    )
    parser.add_argument("paths", nargs="+", help="files or directories to scan")
    args = parser.parse_args(argv)

    total = 0
    for path in _iter_python_files(args.paths):
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"{path}: could not read file: {exc}", file=sys.stderr)
            continue
        try:
            findings = check_source(source, filename=str(path))
        except SyntaxError as exc:
            print(f"{path}:{exc.lineno}: could not parse: {exc.msg}", file=sys.stderr)
            continue
        for finding in findings:
            total += 1
            print(f"{path}:{finding.line}:{finding.col}: {finding.code} {finding.message}")

    if total:
        print(f"\n{total} finding(s)", file=sys.stderr)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
