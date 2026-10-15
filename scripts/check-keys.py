#!/usr/bin/env python3
"""Keys are the one human step. This script makes it a loop: it says which key NAMES each routine
needs and which are missing, never a value. A key lives in one of two places: on this computer,
where `python3 scripts/set-key.py NAME` opens a hidden-input pop-up and writes it into the
credentials file (.env, which only the pop-up and this script touch); or, for the nightly cloud
routines, as a network secret on the routine's cloud environment (the proxy adds the header after
the request leaves, so the variable is empty inside the container).

A `keys:` / `optional_keys:` item is either a bare name (present when the environment or the
credentials file has a value) or an object with `name`, `probe_url`, `header`, `header_prefix`.
An object key is proven by one GET to its probe URL (10 second timeout): the header is sent only
when the variable has a value, so a cloud network secret is proven the same way. 2xx is present,
401/403 is missing, anything else (network error, 5xx, timeout) is "could not check", which never
counts as missing. Slack's auth.test answers 200 even with no token, with a JSON body of ok:false;
a 2xx JSON body with "ok": false therefore counts as missing.

`--where` prints, for each missing key, both places it can go. `--init` copies the shipped example
into the real credentials file once (blank values); use it in a local session only (a cloud
container is thrown away). The agent runs this script; it never opens or names the credentials
file itself (the guard hook forbids that by design). Test hook: CHECK_KEYS_PROBE_RESULTS, a JSON
object {url: status_code | "error"}; when set, no network call is made.

Usage:
  check-keys.py [--vault PATH] [--routine NAME] [--json] [--init] [--where]
Exit: 0 nothing required is missing; 1 something is missing; 2 usage error.
"""
import argparse
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request

ENV_NAME = ".env"
EXAMPLE_NAME = ".env.example"
PROBE_TIMEOUT = 10


def parse_frontmatter(text):
    # Normalize CRLF to LF before matching
    text = text.replace('\r\n', '\n')
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" not in line:
            i += 1
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        k_stripped = k.strip()

        # Block-style YAML list (empty value followed by - items); an item may be an object
        if k_stripped in ("keys", "optional_keys") and v == "":
            items = []
            i += 1
            while i < len(lines) and lines[i].startswith((" ", "\t", "- ")) and lines[i].strip():
                item = lines[i].strip()
                if item.startswith("- "):
                    body = item[2:].strip()
                    if ":" in body and not body.startswith(("'", '"')):
                        ik, _, iv = body.partition(":")
                        items.append({ik.strip(): iv.strip().strip("'\"")})
                    else:
                        items.append(body.strip("'\""))
                elif items and isinstance(items[-1], dict) and ":" in item:
                    ik, _, iv = item.partition(":")
                    items[-1][ik.strip()] = iv.strip().strip("'\"")
                i += 1
            out[k_stripped] = items
        elif v.startswith("[") and v.endswith("]"):
            # Inline list format
            out[k_stripped] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
            i += 1
        else:
            # If key is keys/optional_keys and value is not a list format, error
            if k_stripped in ("keys", "optional_keys") and v:
                # This is a bare scalar like "FOO", not a proper list
                return None
            out[k_stripped] = v.strip("'\"")
            i += 1
    return out


def load_routines(vault):
    routines = {}
    errors = []
    for path in sorted(glob.glob(os.path.join(vault, "System", "routines", "*.md"))):
        with open(path, encoding="utf-8") as f:
            fm = parse_frontmatter(f.read())
        if fm is None:
            name = os.path.splitext(os.path.basename(path))[0]
            errors.append((name, f"routine {name}: keys must be a list"))
            continue
        name = fm.get("name") or os.path.splitext(os.path.basename(path))[0]
        routines[name] = {"title": fm.get("title", name), "keys": fm.get("keys", []) or [],
                          "optional_keys": fm.get("optional_keys", []) or []}
    return routines, errors


def env_names_present(vault):
    """Names with a non-empty value: exported environment first, then the credentials file."""
    present = {k for k, v in os.environ.items() if v}
    try:
        with open(os.path.join(vault, ENV_NAME), encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if v.strip().strip("'\""):
                    k = k.strip()
                    # Strip extra whitespace after export keyword
                    if k.startswith("export "):
                        k = k[7:].lstrip()
                    present.add(k)
    except OSError:
        pass
    return present


def normalize_key(item):
    if isinstance(item, dict):
        return {"name": item.get("name", ""), "probe_url": item.get("probe_url", ""),
                "header": item.get("header", "Authorization"), "header_prefix": item.get("header_prefix", "Bearer ")}
    return {"name": str(item), "probe_url": "", "header": "", "header_prefix": ""}


def says_not_ok(response):
    """True when a 2xx body is a JSON object with "ok": false (Slack's way of refusing a missing or bad token)."""
    try:
        body = json.loads(response.read(65536).decode("utf-8", "replace"))
    except Exception:
        return False
    return isinstance(body, dict) and body.get("ok") is False


def probe_key(spec, value):
    """One GET to the key's probe URL. The header is added only when the variable has a value, so a cloud
    network secret (which the proxy adds after the request leaves) is proven the same way. present: 2xx;
    missing: 401 or 403; unknown: anything else (network error, 5xx, timeout)."""
    fake = os.environ.get("CHECK_KEYS_PROBE_RESULTS")
    if fake:
        code = json.loads(fake).get(spec["probe_url"], "error")
        if code == "error":
            return "unknown"
        code = int(code)
        return "present" if 200 <= code < 300 else ("missing" if code in (401, 403) else "unknown")
    req = urllib.request.Request(spec["probe_url"], headers={"User-Agent": "check-keys"})
    if value:
        req.add_header(spec["header"], f"{spec['header_prefix']}{value}")
    try:
        with urllib.request.urlopen(req, timeout=PROBE_TIMEOUT) as r:
            if not 200 <= r.status < 300:
                return "unknown"
            return "missing" if says_not_ok(r) else "present"
    except urllib.error.HTTPError as e:
        return "missing" if e.code in (401, 403) else "unknown"
    except Exception:
        return "unknown"


def env_value(vault, name):
    """The variable's value: environment first, then the credentials file. Never printed."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        with open(os.path.join(vault, ENV_NAME), encoding="utf-8", errors="replace") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if k.strip().removeprefix("export ").strip() == name:
                    return v.strip().strip("'\"")
    except OSError:
        pass
    return ""


def key_state(vault, spec, present):
    if spec["probe_url"]:
        return probe_key(spec, env_value(vault, spec["name"]))
    return "present" if spec["name"] in present else "missing"


def environment_id(vault):
    try:
        with open(os.path.join(vault, "System", "Routines.md"), encoding="utf-8") as f:
            m = re.search(r"environment id:\s*(env_\w+)", f.read())
            return m.group(1) if m else ""
    except OSError:
        return ""


def where_lines(vault, specs):
    env = environment_id(vault) or "the routine's cloud environment"
    out = []
    for s in specs:
        host = re.sub(r"^https?://([^/]+).*$", r"\1", s["probe_url"]) if s["probe_url"] else "the API's host"
        header = s["header"] or "Authorization"
        prefix = f' with prefix "{s["header_prefix"].strip()}"' if s["header_prefix"].strip() else " with no prefix"
        out.append(f"{s['name']}: on this computer run python3 scripts/set-key.py {s['name']} (a pop-up asks for it); "
                   f"for the nightly routines add it as a network secret on {env} (Allowed websites {host}, "
                   f"header {header}{prefix}).")
    return out


def init_env(vault):
    dst, src = os.path.join(vault, ENV_NAME), os.path.join(vault, EXAMPLE_NAME)
    if os.path.exists(dst):
        return "credentials file already exists; left untouched"
    if not os.path.exists(src):
        return "no example file to copy; nothing created"
    with open(src, encoding="utf-8") as f:
        data = f.read()
    with open(dst, "w", encoding="utf-8") as f:
        f.write(data)
    try:
        os.chmod(dst, 0o600)
    except OSError:
        pass
    return "created the credentials file with blank values; paste each value after its name"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    ap.add_argument("--routine", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--where", action="store_true")
    args = ap.parse_args(argv)

    notes = [init_env(args.vault)] if args.init else []
    routines, errors = load_routines(args.vault)

    # If --routine is specified and that routine has an error, exit 2
    if args.routine:
        for name, msg in errors:
            if name == args.routine:
                print(msg, file=sys.stderr)
                return 2

    # Report other routine errors on stderr but continue (unless --routine specified)
    if args.routine:
        if args.routine not in routines:
            print(f"unknown routine: {args.routine} (known: {', '.join(sorted(routines)) or 'none'})", file=sys.stderr)
            return 2
        routines = {args.routine: routines[args.routine]}
    else:
        # Report errors for all routines only if not filtering
        for name, msg in errors:
            if args.json:
                notes.append(msg)
            else:
                print(msg, file=sys.stderr)

    present = env_names_present(args.vault)
    report, any_missing, where = {}, False, []
    for name, r in routines.items():
        req = [normalize_key(k) for k in r["keys"]]
        opt = [normalize_key(k) for k in r["optional_keys"]]
        states = {s["name"]: key_state(args.vault, s, present) for s in req + opt}
        have = [s["name"] for s in req + opt if states[s["name"]] == "present"]
        missing = [s["name"] for s in req if states[s["name"]] == "missing"]
        opt_missing = [s["name"] for s in opt if states[s["name"]] == "missing"]
        unverified = [s["name"] for s in req + opt if states[s["name"]] == "unknown"]
        any_missing = any_missing or bool(missing)
        report[name] = {"title": r["title"], "present": have, "missing": missing, "optional_missing": opt_missing,
                        "unverified": unverified}
        where.extend(s for s in req + opt if states[s["name"]] == "missing")
    if args.json:
        print(json.dumps({"notes": notes, "routines": report}, indent=1))
    else:
        for n in notes:
            print(n)
        for name, r in report.items():
            line = f"{name} ({r['title']}): present: {', '.join(r['present']) or 'none'}; missing: {', '.join(r['missing']) or 'none'}"
            if r["optional_missing"]:
                line += "; " + ", ".join(k + " (optional)" for k in r["optional_missing"])
            print(line)
            if r["unverified"]:
                print("  could not check (network): " + ", ".join(r["unverified"]))
        if args.where:
            for w in where_lines(args.vault, where):
                print(w)
        elif any_missing:
            print("Run this script with --where to see where each missing key goes.")
    return 1 if any_missing else 0


if __name__ == "__main__":
    sys.exit(main())
