# ratelint

A small static linter that looks for two specific ways Python code gets
itself rate limited or banned by whatever it's talking to:

1. A loop that fires off HTTP-ish calls (`requests.get`, `session.post`,
   `urllib.request.urlopen`, ...) with nothing in the loop that ever sleeps
   or backs off. Fine for ten items, a problem for ten thousand, and the
   difference only shows up once it's already running against production.
2. A route handler (`@app.route`, `@app.get`, `@router.post`, ...) with no
   decorator anywhere near it that looks like a rate limiter. Easy to miss
   when you add a new endpoint next to five others that already have one.

Neither check does real type or import resolution - it's all name matching
on the AST. That means false positives are possible (a loop that calls
`.get()` on a dict will not trip RL001 because `.get` alone isn't enough,
but `.get()` on something named like a session will). Treat findings as
things worth a second look, not certainties.

## Example

```python
# fetch.py
import requests

def sync_all(ids):
    results = []
    for item_id in ids:
        resp = requests.get(f"https://api.example.com/items/{item_id}")
        results.append(resp.json())
    return results


from flask import Flask
app = Flask(__name__)

@app.route("/export")
def export():
    return do_export()
```

```
$ python -m ratelint fetch.py
fetch.py:8:15: RL001 network call inside a loop with no sleep/backoff anywhere in it
fetch.py:17:0: RL002 route handler 'export' has no rate limit decorator

2 finding(s)
```

Adding `time.sleep(0.2)` inside the loop clears the first finding; adding
a decorator with "limit" in its name (e.g. from Flask-Limiter) clears the
second.

## Usage

```
python -m ratelint path/to/file.py
python -m ratelint path/to/package/
```

Pass any number of files or directories. Directories are scanned
recursively for `*.py` files. Exit code is 1 if anything was found, 0
otherwise, so it can be dropped into CI as-is.

## Install

No dependencies, standard library only. Either run it in place from a
checkout:

```
python -m ratelint .
```

or install it locally:

```
pip install -e .
ratelint .
```

## Status

Early. Two rules, both heuristic. See the issue tracker for what's next.
