#!/usr/bin/env python3
"""Keys are the one human step. This script makes it a loop: it says which key NAMES each routine
needs and which are missing, never a value. `--init` copies the shipped example into the real
credentials file once (blank values) so the human has a place to paste; use it in a local session
only (a cloud container is thrown away). The agent runs this script; it never opens or names the
credentials file itself (the guard hook forbids that by design).

Usage:
  check-keys.py [--vault PATH] [--routine NAME] [--json] [--init]
Exit: 0 nothing required is missing; 1 something is missing; 2 usage error.
"""
import argparse
import glob
import json
import os
import re
import sys

ENV_NAME = ".env"
EXAMPLE_NAME = ".env.example"


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            out[k.strip()] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        else:
            out[k.strip()] = v.strip("'\"")
    return out


def load_routines(vault):
    routines = {}
    for path in sorted(glob.glob(os.path.join(vault, "System", "routines", "*.md"))):
        with open(path, encoding="utf-8") as f:
            fm = parse_frontmatter(f.read())
        name = fm.get("name") or os.path.splitext(os.path.basename(path))[0]
        routines[name] = {"title": fm.get("title", name), "keys": fm.get("keys", []) or [],
                          "optional_keys": fm.get("optional_keys", []) or []}
    return routines


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
                    present.add(k[7:] if k.startswith("export ") else k)
    except OSError:
        pass
    return present


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
    args = ap.parse_args(argv)

    notes = [init_env(args.vault)] if args.init else []
    routines = load_routines(args.vault)
    if args.routine:
        if args.routine not in routines:
            print(f"unknown routine: {args.routine} (known: {', '.join(sorted(routines)) or 'none'})", file=sys.stderr)
            return 2
        routines = {args.routine: routines[args.routine]}
    present = env_names_present(args.vault)
    report, any_missing = {}, False
    for name, r in routines.items():
        missing = [k for k in r["keys"] if k not in present]
        have = [k for k in r["keys"] if k in present]
        opt_missing = [k for k in r["optional_keys"] if k not in present]
        any_missing = any_missing or bool(missing)
        report[name] = {"title": r["title"], "present": have, "missing": missing, "optional_missing": opt_missing}
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
        if any_missing:
            print("Paste the missing values after their names in the credentials file at the vault root "
                  "(or the environment settings for cloud runs), then run this again.")
    return 1 if any_missing else 0


if __name__ == "__main__":
    sys.exit(main())
