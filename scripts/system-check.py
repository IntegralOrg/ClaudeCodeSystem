#!/usr/bin/env python3
"""System check: how this vault is configured and whether it is working, read from the vault alone.

Runs nightly as Step 0b of /vault-audit and on demand as /system-check, so a problem is found before the
owner has to explain it, and a fix is confirmed by the next night's run instead of by someone pressing Done.
It never scans the home folder, ~/.claude.json, ~/.config, or anything else outside the vault.

Usage: system-check.py [--vault PATH] [--template PATH] [--today YYYY-MM-DD] [--json] [--no-write]

  --template   a fresh clone of the template (as /update makes); without it, "shipped by the template" is
               read from the vault's own git history and the landing scripts are compared with the last commit.
  --json       print the JSON instead of the summary.
  --no-write   print only; write nothing.

Writes _generated/system-check/<date>.json (for maintainers) and _generated/system-check/<date>.md (the
summary: at most six numbered plain lines, the worst problems first). Nothing else is written. Every
finding carries a severity (blocks cloud, local only, fine) and a tier from docs/DEVELOPING.md "Decision
tiers" (1: the nightly tuning step may fix it; 2: it goes to the template maintainers as names and counts).

Names only, never a value: no key, token, hook command line, note text, or file content is ever printed.
Stdlib only, Python 3.9+, fails open (exit 0 always; a check that cannot run becomes a "fine" finding).
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "hooks"))
import landing_health  # noqa: E402  (the session-start landing notice; reused, never copied)
import routine_health  # noqa: E402  (the session-start routine notice; reused, never copied)
from guard_vault_path import synced_service  # noqa: E402


def _load(name, path):
    try:
        spec = importlib.util.spec_from_file_location(name, str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


telemetry = _load("system_check_telemetry", HERE / "system-journal" / "telemetry-stats.py")
check_keys = _load("system_check_keys", HERE / "check-keys.py")
log_tool_use = _load("system_check_mask", HERE / "hooks" / "log_tool_use.py")

SEVERITIES = ("blocks cloud", "local only", "fine")
# Order the summary reads in: the incident class first, then setup, then the rest.
SECTIONS = ("landing safety", "configuration", "deterministic pieces", "routines and hooks", "connectors",
            "cloud brain", "needs a look", "history")

# The template's hooks, by event and script (kept equal to .claude/settings.json by test_system_check.py).
EXPECTED_HOOKS = (
    "PostToolUse: scripts/hooks/bump_updated.py", "PostToolUse: scripts/hooks/log_tool_use.py",
    "PostToolUseFailure: scripts/hooks/log_tool_use.py",
    "PreToolUse: scripts/hooks/guard_secrets.py", "PreToolUse: scripts/hooks/guard_state_writes.py",
    "SessionEnd: scripts/cloud-land.sh --final", "SessionEnd: scripts/land-local.sh --final",
    "SessionEnd: scripts/system-journal/cloud-journal.sh --final",
    "SessionStart: scripts/cloud-land.sh --start", "SessionStart: scripts/hooks/guard_vault_path.py",
    "SessionStart: scripts/hooks/landing_health.py", "SessionStart: scripts/hooks/routine_health.py",
    "SessionStart: scripts/hooks/session_context.py", "SessionStart: scripts/hooks/setup_pending.py",
    "SessionStart: scripts/hooks/tools_health.py", "SessionStart: scripts/land-local.sh --pull",
    "Stop: scripts/cloud-land.sh", "Stop: scripts/land-local.sh", "Stop: scripts/system-journal/cloud-journal.sh",
)
EXPECTED_HOOK_FILES = ("_common.py", "bump_updated.py", "guard_secrets.py", "guard_state_writes.py", "guard_vault_path.py",
                       "landing_health.py", "log_tool_use.py", "routine_health.py", "session_context.py", "setup_pending.py",
                       "tools_health.py")
EXPECTED_DENY = ("Read(./.env)", "Read(./.env.*)", "Read(./**/.env)", "Read(./**/.env.*)")
EXPECTED_ALLOW = ("Read", "Edit", "Write", "Bash(*)")
LANDING_SCRIPTS = ("scripts/land-local.sh", "scripts/cloud-land.sh")

SCRIPT_EXTS = (".py", ".sh", ".js", ".mjs", ".ts", ".ps1")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".playwright-mcp"}
SKIP_PREFIXES = (".claude/worktrees/",)
HOME_PATH_RE = re.compile(r"(/Users/[^/\s\"'$]+/|/home/(?!user/)[^/\s\"'$]+/|[A-Za-z]:\\+Users\\+)")
OUTSIDE_RE = re.compile(r"Path\.home\(\)|expanduser\(|[\"']~/|~/\.config|\$HOME\b|%USERPROFILE%|"
                        r"environ(?:\.get\(|\[)\s*[\"'](?:HOME|USERPROFILE)[\"']|/Users/[^/\s\"'$]+/")
PLACEHOLDER_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*(?::-[^}]*)?\}")
SECRETISH_RE = re.compile(r"(key|token|secret|password|passwd|credential|auth)", re.I)
NUMBERED_RE = re.compile(r"^(?P<stem>.+) (?P<n>\d{1,3})(?P<ext>\.[A-Za-z0-9]+)$")
LANDING_SUBJECT_RE = re.compile(r"^(Cloud session|Session) ([0-9a-f]{4,})\b.*: land .*\(hook\)$")
RATE_RE = re.compile(r"429|rate.?limit", re.I)
BAD_CONNECTOR_RE = re.compile(r"\b(missing|404|not connected|absent|connector-missing)\b", re.I)

MASS_DELETE = 10        # a landing commit deleting more files than this is a finding
UNTOUCHED_MAX = 10      # a cloud landing changing more files than this that its session never touched
NUMBERED_TIER2 = 5      # more numbered copies than this goes to the maintainers
RATE_WEEK = 5           # rate limits self-heal: fine below this many in 7 days
ERROR_REPEAT = 3        # an error class seen this often in 30 days is listed
ERROR_LOUD = 10         # and counts as a problem from here
STALE_BRANCH_DAYS = 3
REFUSAL_WINDOW = 7
ALERT_DAYS = 7

TIER1_FIX = "The nightly tuning step rewrites the wording that causes it; nothing for you to do"
TIER2_FIX = "Goes to your contact as a report of names and counts; nothing for you to do"


class Ctx:
    def __init__(self, root, today, template):
        self.root = root
        self.today = today
        self.template = template
        self.facts = {}
        self.findings = []
        self._tracked = False

    def add(self, fid, section, severity, tier, title, fix, page, count=None, paths=None, detail="", **extra):
        f = {"id": fid, "section": section, "severity": severity, "tier": tier, "title": title, "fix": fix, "page": page,
             "count": count if count is not None else 1, "paths": sorted(paths or [])[:20], "detail": detail}
        f.update({k: v for k, v in extra.items() if v is not None})
        self.findings.append(f)

    def git(self, *args, timeout=20):
        try:
            p = subprocess.run(["git", "--no-optional-locks", "-C", str(self.root), *args], capture_output=True, text=True,
                               timeout=timeout)
            return p.stdout if p.returncode == 0 else None
        except Exception:
            return None

    @property
    def tracked(self):
        """Tracked paths, or None when the vault is not a git work tree."""
        if self._tracked is False:
            out = self.git("ls-files", "-z")
            self._tracked = set(out.split("\0")) - {""} if out is not None else None
        return self._tracked


def n_of(n, one, many=None):
    """`1 file`, `3 files`: plain counts for the summary."""
    return f"{n} {one if n == 1 else (many or one + 's')}"


def times(n):
    return "once" if n == 1 else f"{n} times"


def rel(root, p):
    return Path(p).relative_to(root).as_posix()


def walk(root):
    """Every file under the vault, skipping VCS, caches and agent worktrees."""
    for dirpath, dirnames, filenames in os.walk(str(root)):
        r = Path(dirpath).relative_to(root).as_posix()
        r = "" if r == "." else r + "/"
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not any((r + d + "/").startswith(s) for s in SKIP_PREFIXES)]
        for f in filenames:
            yield r + f


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def same_bytes(a, b):
    try:
        return Path(a).read_bytes().replace(b"\r\n", b"\n") == Path(b).read_bytes().replace(b"\r\n", b"\n")
    except Exception:
        return False


# ----------------------------------------------------------------------------- 1. configuration

def hook_name(event, command):
    """`<event>: <script>[ --flag]`. Never the command line itself: it can carry an inline value."""
    m = re.search(r"\$\{?CLAUDE_PROJECT_DIR\}?/([^\"'\s]+)", command)
    script = m.group(1) if m else None
    tail = command[m.end():] if m else ""
    if not script:
        found = list(re.finditer(r"([^\s\"'/\\]+\.(?:py|sh|js|mjs|ps1))(?=[\"'\s]|$)", command))
        if not found:
            return f"{event}: (inline command)"
        script, tail = found[-1].group(1), command[found[-1].end():]
    flags = [a for a in tail.replace('"', " ").replace("'", " ").split() if re.fullmatch(r"--?[A-Za-z][\w-]*", a)]
    return f"{event}: {script}" + "".join(" " + f for f in flags)


def hook_commands(settings):
    for event, groups in ((settings or {}).get("hooks") or {}).items():
        for g in groups or []:
            for h in (g or {}).get("hooks") or []:
                if isinstance(h, dict) and isinstance(h.get("command"), str):
                    yield event, h["command"]


def expected_hooks(settings):
    return sorted({hook_name(e, c) for e, c in hook_commands(settings)})


def check_configuration(ctx):
    path = ctx.root / ".claude" / "settings.json"
    if not path.is_file():
        ctx.add("settings-missing", "configuration", "blocks cloud", 2, "The settings file that switches on the safety hooks is missing",
                "Take .claude/settings.json from the template with /update", "System/Updating.md", paths=[".claude/settings.json"])
        settings = None
    else:
        settings = read_json(path)
        if not isinstance(settings, dict):
            ctx.add("settings-invalid", "configuration", "blocks cloud", 2, "The settings file cannot be read",
                    TIER2_FIX, "System/Who Decides.md", paths=[".claude/settings.json"])
            settings = None
    tpl = read_json(ctx.template / ".claude" / "settings.json") if ctx.template else None
    if settings is not None:
        want = set(expected_hooks(tpl)) if isinstance(tpl, dict) else set(EXPECTED_HOOKS)
        have = set(expected_hooks(settings))
        missing = sorted(want - have)
        if missing:
            ctx.add("hooks-missing", "configuration", "blocks cloud", 2, f"{len(missing)} of the system's hooks are switched off",
                    TIER2_FIX, "System/Who Decides.md", count=len(missing), paths=[".claude/settings.json"], names=missing,
                    detail="Without them a cloud run does not save its work or the guard rails do not run.")
        extra = sorted(have - want)
        if extra:
            ctx.add("hooks-extra", "configuration", "fine", 2, f"{n_of(len(extra), 'hook')} added that the template does not ship",
                    TIER2_FIX, "System/Who Decides.md", count=len(extra), paths=[".claude/settings.json"], names=extra)
        outside, relative = [], []
        for event, cmd in hook_commands(settings):
            if HOME_PATH_RE.search(cmd) or (re.search(r"(^|\s|[\"'])/(?!tmp/)", cmd) and "CLAUDE_PROJECT_DIR" not in cmd):
                outside.append(hook_name(event, cmd))
            elif "CLAUDE_PROJECT_DIR" not in cmd:
                relative.append(hook_name(event, cmd))
        if outside:
            names = sorted(set(outside))
            what = names[0].split(": ", 1)[1].split(" ")[0] if len(names) == 1 else f"{len(names)} scripts"
            ctx.add("hook-outside-vault", "configuration", "blocks cloud", 2, f"A hook runs {what} from outside the vault",
                    TIER2_FIX, "System/Who Decides.md", count=len(names), paths=[".claude/settings.json"], names=names,
                    detail="In the cloud: the container holds only this repository, so the hook finds nothing to run.")
        if relative:
            ctx.add("hook-no-project-dir", "configuration", "local only", 2,
                    f"{n_of(len(set(relative)), 'hook depends', 'hooks depend')} on the folder the session starts in", TIER2_FIX, "System/Who Decides.md",
                    count=len(set(relative)), paths=[".claude/settings.json"], names=sorted(set(relative)))
        perms = settings.get("permissions") or {}
        tperms = (tpl or {}).get("permissions") or {} if isinstance(tpl, dict) else {}
        want_deny = tperms.get("deny") if tperms.get("deny") is not None else EXPECTED_DENY
        want_allow = tperms.get("allow") if tperms.get("allow") is not None else EXPECTED_ALLOW
        no_deny = sorted(set(want_deny) - set(perms.get("deny") or []))
        no_allow = sorted(set(want_allow) - set(perms.get("allow") or []))
        if no_deny:
            ctx.add("deny-rules-missing", "configuration", "local only", 2,
                    "The rule that keeps the agent out of the credentials file is missing", TIER2_FIX, "System/Who Decides.md",
                    count=len(no_deny), paths=[".claude/settings.json"])
        if no_allow:
            ctx.add("allow-rules-missing", "configuration", "blocks cloud", 2,
                    f"{n_of(len(no_allow), 'permission')} the routines rely on missing, so a routine stops on a prompt",
                    TIER2_FIX, "System/Who Decides.md", count=len(no_allow), paths=[".claude/settings.json"], names=no_allow)
    mcp_path = ctx.root / ".mcp.json"
    if mcp_path.is_file():
        mcp = read_json(mcp_path)
        servers = (mcp or {}).get("mcpServers") if isinstance(mcp, dict) else None
        if not isinstance(servers, dict):
            ctx.add("mcp-invalid", "configuration", "local only", 2, "The tools file (.mcp.json) cannot be read", TIER2_FIX,
                    "System/Who Decides.md", paths=[".mcp.json"])
            return
        inline, inline_servers, outside = 0, set(), set()
        for name, srv in servers.items():
            if not isinstance(srv, dict):
                continue
            values = []
            for field in ("env", "headers"):
                if isinstance(srv.get(field), dict):
                    values += [v for v in srv[field].values() if isinstance(v, str)]
            for a in srv.get("args") or []:
                if isinstance(a, str) and "=" in a and SECRETISH_RE.search(a.split("=", 1)[0]):
                    values.append(a.split("=", 1)[1])
            n = sum(1 for v in values if v.strip() and not PLACEHOLDER_RE.search(v))
            if n:
                inline += n
                inline_servers.add(str(name))
            cmd = " ".join(str(x) for x in [srv.get("command") or ""] + list(srv.get("args") or []))
            if HOME_PATH_RE.search(cmd):
                outside.add(str(name))
        ctx.facts["mcp_servers"] = len(servers)
        if inline:
            ctx.add("mcp-inline-values", "configuration", "local only", 2,
                    f"{n_of(inline, 'value is', 'values are')} written straight into the tools file instead of a ${{NAME}} placeholder",
                    TIER2_FIX, "System/Connecting Tools.md", count=inline, paths=[".mcp.json"], names=sorted(inline_servers),
                    detail="A value committed to the repository travels with every copy of it; the cloud reads ${NAME} from the environment.")
        if outside:
            ctx.add("mcp-outside-vault", "configuration", "blocks cloud", 2, f"{n_of(len(outside), 'tool starts', 'tools start')} a program from this computer's home folder",
                    TIER2_FIX, "System/Connecting Tools.md", count=len(outside), paths=[".mcp.json"], names=sorted(outside),
                    detail="In the cloud: that program does not exist there, so the tool never starts.")


# ----------------------------------------------------------------------------- 2. needs a look

def shipped_files(ctx):
    """Paths the template ships: the template clone when given, else files the vault's history got from the
    template (its first commit and every `Update from the template` commit). None when neither is known."""
    if ctx.template:
        return {p for p in walk(ctx.template)}
    roots = ctx.git("rev-list", "--max-parents=0", "HEAD")
    if roots is None:
        return None
    out = set()
    for sha in roots.split():
        listing = ctx.git("ls-tree", "-r", "--name-only", sha)
        out.update((listing or "").splitlines())
    log = ctx.git("log", "--diff-filter=A", "--name-only", "--format=%x01%s", "HEAD", timeout=60) or ""
    for block in log.split("\x01")[1:]:
        lines = block.splitlines()
        if lines and lines[0].startswith("Update from the template"):
            out.update(l for l in lines[1:] if l.strip())
    return out


def check_needs_a_look(ctx):
    shipped = shipped_files(ctx)
    ctx.facts["template"] = "compared" if ctx.template else ("history" if shipped is not None else "not compared")
    scripts = [p for p in walk(ctx.root) if p.endswith(SCRIPT_EXTS) and not p.startswith("_generated/")]
    to_scan = []
    if shipped is not None:
        stray = sorted(p for p in scripts if p not in shipped)
        if stray:
            ctx.add("script-not-from-template", "needs a look", "fine", 2, f"{n_of(len(stray), 'script')} in the vault did not come from the template",
                    TIER2_FIX, "System/Who Decides.md", count=len(stray), paths=stray)
        to_scan = stray
        if ctx.template:
            to_scan += [p for p in scripts if p in shipped and not same_bytes(ctx.root / p, ctx.template / p)]
    reads = []
    for p in sorted(set(to_scan)):
        try:
            text = (ctx.root / p).read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if OUTSIDE_RE.search(text):
            reads.append(p)
    if reads:
        ctx.add("script-reads-outside-vault", "needs a look", "blocks cloud", 2,
                f"{n_of(len(reads), 'script reads its', 'scripts read their')} settings from outside the vault", TIER2_FIX, "System/Who Decides.md",
                count=len(reads), paths=reads,
                detail="In the cloud: there is no home folder and nothing outside the repository, so the script finds no settings and fails.")
    nested = [p[:-len("/.git")] if p.endswith("/.git") else p for p in walk(ctx.root) if p.endswith("/.git")]
    for dirpath, dirnames, _ in os.walk(str(ctx.root)):
        r = Path(dirpath).relative_to(ctx.root).as_posix()
        if r != "." and ".git" in dirnames and not any((r + "/").startswith(s) for s in SKIP_PREFIXES):
            nested.append(r)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    if (ctx.root / ".gitmodules").is_file():
        nested.append(".gitmodules")
    if nested:
        ctx.add("second-repository", "needs a look", "blocks cloud", 2, f"{n_of(len(set(nested)), 'other repository sits', 'other repositories sit')} inside the vault",
                TIER2_FIX, "System/Who Decides.md", count=len(set(nested)), paths=sorted(set(nested)),
                detail="In the cloud: only this repository is checked out, so whatever relies on the other one breaks.")
    outside = []
    for f in sorted((ctx.root / "System" / "routines").glob("*.md")):
        try:
            if HOME_PATH_RE.search(f.read_text(encoding="utf-8", errors="replace")):
                outside.append(rel(ctx.root, f))
        except Exception:
            continue
    if outside:
        ctx.add("routine-outside-vault", "needs a look", "blocks cloud", 2, f"{n_of(len(outside), 'routine points', 'routines point')} at a folder on one computer",
                TIER2_FIX, "System/Routines.md", count=len(outside), paths=outside,
                detail="In the cloud: a routine runs in a fresh container where that folder does not exist.")


# ----------------------------------------------------------------------------- 3. deterministic pieces

IMPORT_PROBE = r"""
import importlib.util, json, os, sys
out = []
for path in sys.argv[1:]:
    name = os.path.basename(path)
    try:
        spec = importlib.util.spec_from_file_location("probe_" + name[:-3], path)
        spec.loader.exec_module(importlib.util.module_from_spec(spec))
    except BaseException as e:
        out.append([name, type(e).__name__])
print(json.dumps(out))
"""


def check_deterministic(ctx):
    hooks_dir = ctx.root / "scripts" / "hooks"
    want = ({p.name for p in (ctx.template / "scripts" / "hooks").glob("*.py")} if ctx.template else set(EXPECTED_HOOK_FILES))
    missing = sorted(n for n in want if not (hooks_dir / n).is_file())
    if missing:
        ctx.add("hook-file-missing", "deterministic pieces", "blocks cloud", 2, f"{n_of(len(missing), 'hook script is', 'hook scripts are')} missing",
                "Take them from the template with /update", "System/Updating.md", count=len(missing),
                paths=["scripts/hooks/" + n for n in missing])
    present = sorted(str(hooks_dir / n) for n in want if (hooks_dir / n).is_file())
    if present:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        try:
            p = subprocess.run([sys.executable, "-c", IMPORT_PROBE, *present], capture_output=True, text=True, timeout=60,
                               cwd=str(hooks_dir), env=env, stdin=subprocess.DEVNULL)
            broken = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else [["(all)", "no output"]]
        except Exception as e:
            broken = [["(all)", type(e).__name__]]
        if broken:
            ctx.add("hook-import-failed", "deterministic pieces", "blocks cloud", 2, f"{n_of(len(broken), 'hook script fails', 'hook scripts fail')} to load",
                    TIER2_FIX, "System/Who Decides.md", count=len(broken), paths=["scripts/hooks/" + b[0] for b in broken],
                    error_class=",".join(sorted({b[1] for b in broken})))
    compared = []
    for r in LANDING_SCRIPTS:
        p = ctx.root / r
        if not p.is_file():
            ctx.add("landing-script-missing:" + Path(r).name, "deterministic pieces", "blocks cloud", 2,
                    f"The script that saves work to GitHub ({Path(r).name}) is missing", "Take it from the template with /update",
                    "System/Updating.md", paths=[r])
            continue
        if ctx.template and (ctx.template / r).is_file():
            compared.append("template")
            if not same_bytes(p, ctx.template / r):
                ctx.add("landing-script-changed:" + Path(r).name, "deterministic pieces", "blocks cloud", 2,
                        f"The script that saves work to GitHub ({Path(r).name}) differs from the template", TIER2_FIX,
                        "System/Who Decides.md", paths=[r])
        elif ctx.git("rev-parse", "--is-inside-work-tree") is not None:
            compared.append("last commit")
            if ctx.git("diff", "--quiet", "HEAD", "--", r) is None and ctx.git("cat-file", "-e", "HEAD:" + r) is not None:
                ctx.add("landing-script-edited:" + Path(r).name, "deterministic pieces", "local only", 2,
                        f"The script that saves work to GitHub ({Path(r).name}) was edited on this computer", TIER2_FIX,
                        "System/Who Decides.md", paths=[r])
    ctx.facts["landing_scripts_compared_to"] = sorted(set(compared)) or "not compared"
    ctx.facts["python3"] = bool(shutil.which("python3") or sys.executable)
    ctx.facts["git"] = bool(shutil.which("git"))
    if not ctx.facts["git"]:
        ctx.add("git-missing", "deterministic pieces", "local only", 2, "Git is not installed on this computer, so nothing here is saved to GitHub",
                "Install it as System/Adding Your Computer.md shows", "System/Adding Your Computer.md")
    ck = ctx.root / "scripts" / "check-keys.py"
    if not ck.is_file():
        ctx.add("check-keys-missing", "deterministic pieces", "local only", 2, "The key checker (check-keys.py) is missing",
                "Take it from the template with /update", "System/Updating.md", paths=["scripts/check-keys.py"])
        return
    try:
        p = subprocess.run([sys.executable, str(ck), "--vault", str(ctx.root), "--json"], capture_output=True, text=True,
                           timeout=30, stdin=subprocess.DEVNULL)
        report = json.loads(p.stdout).get("routines") or {}
    except Exception:
        report = {}
    ctx.facts["keys_missing"] = {}
    for name, r in sorted(report.items()):
        missing = [str(k) for k in (r.get("missing") or [])]
        ctx.facts["keys_missing"][name] = missing
        if missing:
            ctx.add("key-missing:" + name, "deterministic pieces", "blocks cloud", 2,
                    f"The {r.get('title') or name} routine is missing {n_of(len(missing), 'key')}",
                    "Add each named key to the environment settings", "System/Connecting Tools.md", count=len(missing),
                    names=missing, routine=name)


# ----------------------------------------------------------------------------- 4. routines and hooks

def now_iso(ctx):
    return f"{ctx.today.isoformat()}T23:59:59+00:00"


def check_routines(ctx):
    live = routine_health.parse_routines(ctx.root)
    ctx.facts["live_since"] = {k: (v.isoformat() if v else None) for k, v in sorted(live.items())}
    hyg = routine_health.newest_audit_heading(ctx.root)
    ctx.facts["vault_hygiene_last_run"] = hyg.isoformat() if hyg else None
    for text in routine_health.problems(ctx.root, ctx.today):
        m = re.match(r"^Routine (.+?) (has not run since|is still not live)", text)
        if not m:
            continue  # the missing key or connector lines are section 8's
        slug = re.sub(r"[^a-z0-9]+", "-", m.group(1).lower()).strip("-")
        kind = "routine-not-running" if m.group(2).startswith("has") else "routine-not-live"
        ctx.add(f"{kind}:{slug}", "routines and hooks", "blocks cloud", 2, text, "Open System/Routines.md and check the routine is scheduled",
                "System/Routines.md", routine=slug)
    cutoff = datetime.combine(ctx.today - timedelta(days=7), datetime.min.time()).isoformat()
    sessions = set()
    for f in sorted((ctx.root / "_generated" / "agent-actions").glob("*.jsonl")):
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and str(row.get("ts", ""))[:19] >= cutoff and row.get("session_id"):
                    sessions.add(row["session_id"])
        except Exception:
            continue
    evidence = len(telemetry.load_records(str(ctx.root), 7, now_iso(ctx))) if telemetry else None
    ctx.facts["sessions_7d"], ctx.facts["evidence_7d"] = len(sessions), evidence
    if sessions and evidence is not None and len(sessions) >= 3 and evidence == 0:
        ctx.add("journal-not-capturing", "routines and hooks", "local only", 2,
                f"The session journal recorded none of this week's {len(sessions)} sessions", TIER2_FIX, "System/Who Decides.md",
                count=len(sessions))
    lines = landing_health.log_lines(ctx.root)
    ctx.facts["landing_log"] = None if lines is None else {
        "lines": len(lines), "ever_landed": any("landed on main" in l or "nothing to" in l for l in lines),
        "ever_pulled": any(" pull: " in l for l in lines)}
    if lines:
        if not ctx.facts["landing_log"]["ever_landed"]:
            ctx.add("landing-never-succeeded", "routines and hooks", "local only", 2, "This computer has never saved work to GitHub",
                    TIER2_FIX, "System/Adding Your Computer.md", paths=["_generated/landing.log"])
        if not ctx.facts["landing_log"]["ever_pulled"]:
            ctx.add("pull-never-ran", "routines and hooks", "local only", 2,
                    "Sessions on this computer never fetch the newest copy from GitHub when they start", TIER2_FIX,
                    "System/Adding Your Computer.md", paths=["_generated/landing.log"])


# ----------------------------------------------------------------------------- 5. history

def check_history(ctx):
    bad = []
    for f in sorted((ctx.root / "_generated" / "system-journal" / "evidence").glob("*/*.json")):
        if not isinstance(read_json(f), dict):
            bad.append(rel(ctx.root, f))
    for f in sorted((ctx.root / "_generated" / "agent-actions").glob("*.jsonl")):
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip():
                    json.loads(line)
        except ValueError:
            bad.append(rel(ctx.root, f))
        except Exception:
            continue
    if bad:
        ctx.add("history-unreadable", "history", "fine", 2, f"{n_of(len(bad), 'record file')} cannot be read", TIER2_FIX,
                "System/Who Decides.md", count=len(bad), paths=bad)
    if not telemetry:
        return
    records = [r for r in telemetry.load_records(str(ctx.root), 30, now_iso(ctx)) if not r.get("private")]
    week = (ctx.today - timedelta(days=6)).isoformat()
    classes, rates = {}, {}
    for r in records:
        for ts, t in telemetry.calls_of(r):
            if t.get("ok") is not False:
                continue
            day = str(ts or r.get("ended") or "")[:10] or ctx.today.isoformat()
            cls = t.get("error_class") or "tool_error"
            if RATE_RE.search(cls):
                name = t.get("name") or "?"
                m = re.match(r"^mcp__(.+?)__", name)
                key = m.group(1) if m else name
                agg = rates.setdefault(key, {"count": 0, "week": 0, "first": day, "last": day})
            else:
                key = cls
                agg = classes.setdefault(key, {"count": 0, "week": 0, "first": day, "last": day})
            agg["count"] += 1
            agg["week"] += day >= week
            agg["first"], agg["last"] = min(agg["first"], day), max(agg["last"], day)
    ctx.facts["error_classes_30d"] = {k: v["count"] for k, v in sorted(classes.items(), key=lambda kv: (-kv[1]["count"], kv[0]))}
    ctx.facts["rate_limits_30d"] = {k: v["count"] for k, v in sorted(rates.items())}
    for cls, v in sorted(classes.items()):
        if v["count"] < ERROR_REPEAT:
            continue
        tier = 1 if cls in ("hook_blocked", "tool_error") or cls.startswith("exit_") else 2
        if cls == "hook_blocked":
            title = f"The safety rules blocked the agent {v['count']} times in 30 days"
        elif cls == "permission_denied":
            title = f"The agent was refused permission {v['count']} times in 30 days"
        else:
            title = f"Tool calls failed with {cls} {v['count']} times in 30 days"
        ctx.add("error-class:" + cls, "history", "local only" if v["count"] >= ERROR_LOUD else "fine", tier, title,
                TIER1_FIX if tier == 1 else TIER2_FIX, "System/Who Decides.md", count=v["count"], first=v["first"],
                last=v["last"], error_class=cls)
    for key, v in sorted(rates.items()):
        if not v["week"]:
            continue
        ctx.add("rate-limit:" + key, "history", "local only" if v["week"] >= RATE_WEEK else "fine", 2,
                f"{key} asked the agent to slow down {v['week']} times this week",
                "These clear on their own; past five a week they go to your contact", "System/Who Decides.md",
                count=v["week"], first=v["first"], last=v["last"], error_class="rate_limited")


# ----------------------------------------------------------------------------- 6. cloud brain

def check_cloud_brain(ctx):
    if ctx.git("rev-parse", "--is-inside-work-tree") is None:
        ctx.facts["git_repository"] = False
        return
    ctx.facts["git_repository"] = True
    if ctx.git("rev-parse", "--verify", "-q", "main") is not None and ctx.git("rev-parse", "--verify", "-q", "origin/main") is not None:
        out = (ctx.git("rev-list", "--left-right", "--count", "main...origin/main") or "0 0").split()
        ahead, behind = int(out[0]), int(out[1])
        ctx.facts["main_vs_origin"] = {"ahead": ahead, "behind": behind, "as_of": "last fetch"}
        if ahead:
            ctx.add("main-ahead", "cloud brain", "local only", 2, f"{n_of(ahead, 'saved change')} on this computer not yet on GitHub",
                    "The next session saves them; if this stays, the landing notice says why", "System/Adding Your Computer.md",
                    count=ahead)
    refs = ctx.git("for-each-ref", "--format=%(refname:short)%09%(committerdate:short)", "refs/heads/claude", "refs/remotes/origin/claude") or ""
    stale = []
    for line in refs.splitlines():
        name, _, when = line.partition("\t")
        try:
            if (ctx.today - date.fromisoformat(when.strip())).days > STALE_BRANCH_DAYS:
                stale.append(name.strip())
        except ValueError:
            continue
    if stale:
        ctx.add("stale-claude-branches", "cloud brain", "blocks cloud", 2,
                f"{n_of(len(stale), 'cloud working branch', 'cloud working branches')} never folded into main", TIER2_FIX, "System/Who Decides.md",
                count=len(stale), names=sorted(stale))
    origin = ctx.git("remote", "get-url", "origin") or ""
    if "github.com" in origin and shutil.which("gh"):
        try:
            p = subprocess.run(["gh", "pr", "list", "--state", "open", "--json", "number,headRefName", "--limit", "50"],
                               cwd=str(ctx.root), capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
            prs = json.loads(p.stdout) if p.returncode == 0 else None
        except Exception:
            prs = None
        ctx.facts["open_pull_requests"] = None if prs is None else len(prs)
        if prs:
            ctx.add("open-pull-requests", "cloud brain", "local only", 2, f"{n_of(len(prs), 'pull request is', 'pull requests are')} open, so that work is not on main",
                    TIER2_FIX, "System/Who Decides.md", count=len(prs), names=sorted(str(x.get("headRefName")) for x in prs))
    wf = ctx.root / ".github" / "workflows" / "vault-autosync.yml"
    if not wf.is_file():
        ctx.add("autosync-missing", "cloud brain", "blocks cloud", 2, "The safety net that folds cloud branches into main is missing",
                "Take .github/workflows/vault-autosync.yml from the template with /update", "System/Updating.md",
                paths=[".github/workflows/vault-autosync.yml"])
    else:
        text = wf.read_text(encoding="utf-8", errors="replace")
        if "concurrency:" not in text or "github.repository" not in text:
            ctx.add("autosync-unguarded", "cloud brain", "fine", 2, "The autosync workflow lost its guard lines", TIER2_FIX,
                    "System/Who Decides.md", paths=[".github/workflows/vault-autosync.yml"])


# ----------------------------------------------------------------------------- 7. landing safety

def touched_by(ctx, sid8):
    """Files a session's evidence says it touched, or None when there is no readable, non-private record."""
    for f in (ctx.root / "_generated" / "system-journal" / "evidence").glob(f"*/{sid8}*.json"):
        rec = read_json(f)
        if isinstance(rec, dict) and not rec.get("private"):
            return [str(p).replace("\\", "/") for p in rec.get("files_touched") or []]
    return None


def check_landing(ctx):
    markers = landing_health.refusal_markers(ctx.root, days=REFUSAL_WINDOW, today=ctx.today)
    stale = [m["stale_at_start"] for m in markers if m["stale_at_start"] is not None]
    if markers:
        ctx.add("cloud-refusal", "landing safety", "blocks cloud", 2,
                f"A cloud session's changes could not be saved to main ({times(len(markers))} this week)", TIER2_FIX,
                "System/Who Decides.md", count=len(markers), first=markers[0]["date"], last=markers[-1]["date"],
                paths=["_generated/landing/cloud-refusals/" + m["file"] for m in markers])
    container = Path("/root/.cloud-land/start-stale")
    try:
        if container.is_file():
            stale.append(int(container.read_text().strip() or 0))
    except Exception:
        pass
    ctx.facts["stale_at_start_max"] = max(stale) if stale else None
    if stale and max(stale) > 0:
        ctx.add("stale-container", "landing safety", "fine", 2,
                f"A cloud session started from a copy {n_of(max(stale), 'file')} older than main (handled, nothing was lost)",
                TIER2_FIX, "System/Who Decides.md", count=max(stale))
    branch = "main" if ctx.git("rev-parse", "--verify", "-q", "main") is not None else "HEAD"
    log = ctx.git("log", "-n", "300", "--format=%x01%H%x09%cs%x09%s", branch, timeout=30) or ""
    landings = []
    for block in log.split("\x01")[1:]:
        sha, when, subject = (block.strip().split("\t", 2) + ["", ""])[:3]
        m = LANDING_SUBJECT_RE.match(subject)
        if m:
            landings.append((sha, when, m.group(1), m.group(2)))
        if len(landings) >= 10:
            break
    deleted, del_commits, untouched, unt_commits, del_paths, unt_paths = 0, [], 0, [], [], []
    for sha, when, kind, sid8 in landings:
        status = ctx.git("show", "--name-status", "--no-renames", "--format=", sha) or ""
        dels = [l for l in status.splitlines() if l.startswith("D\t")]
        if len(dels) > MASS_DELETE:
            deleted += len(dels)
            del_commits.append((sha[:7], when))
            del_paths += [l.split("\t", 1)[1] for l in dels]
        if kind == "Cloud session":
            touched = touched_by(ctx, sid8)
            if touched is None:
                continue
            changed = [l.split("\t", 1)[1] for l in status.splitlines() if l[:1] in "MD" and "\t" in l]
            never = [p for p in changed if not p.startswith("_generated/")
                     and not any(t == p or t.endswith("/" + p) for t in touched)]
            if len(never) > UNTOUCHED_MAX:
                untouched += len(never)
                unt_commits.append((sha[:7], when))
                unt_paths += never
    ctx.facts["landing_commits_checked"] = len(landings)
    if del_commits:
        ctx.add("landing-mass-deletion", "landing safety", "blocks cloud", 2,
                f"A save to GitHub deleted {deleted} files at once", TIER2_FIX, "System/Who Decides.md", count=deleted,
                first=min(w for _, w in del_commits), last=max(w for _, w in del_commits), names=[s for s, _ in del_commits],
                paths=del_paths)
    if unt_commits:
        ctx.add("landing-untouched-changes", "landing safety", "blocks cloud", 2,
                f"A cloud save changed {untouched} files its session never touched", TIER2_FIX, "System/Who Decides.md",
                count=untouched, first=min(w for _, w in unt_commits), last=max(w for _, w in unt_commits),
                names=[s for s, _ in unt_commits], paths=unt_paths)
    kinds = (("synced folder", "landing-synced-folder", "Saving to GitHub is paused because the vault sits in a synced folder",
              "Move the vault out of the synced folder, step 2", "System/Adding Your Computer.md"),
             ("could not fetch", "landing-fetch", "This computer cannot reach GitHub, so work is not being saved there",
              "Check the sign-in, step 4", "System/Adding Your Computer.md"),
             ("has failed", "landing-failed", "Saving to GitHub keeps failing on this computer", TIER2_FIX, "System/Who Decides.md"),
             ("appears disabled", "landing-disabled", "Saving to GitHub appears switched off on this computer", TIER2_FIX,
              "System/Who Decides.md"))
    for notice in landing_health.notices(ctx.root):
        if notice.startswith("Cloud session "):
            continue  # refusal markers are reported above, over the longer window
        for word, fid, title, fix, page in kinds:
            if word in notice:
                n = re.search(r"(\d+) time", notice)
                ctx.add(fid, "landing safety", "local only", 2, title, fix, page, count=int(n.group(1)) if n else 1,
                        paths=["_generated/landing.log"])
                break
    tracked = ctx.tracked
    copies = []
    for p in walk(ctx.root):
        name = p.rsplit("/", 1)[-1]
        m = NUMBERED_RE.match(name)
        if not m:
            continue
        base = (p[: -len(name)] + m.group("stem") + m.group("ext"))
        if tracked is not None:
            if base in tracked and p not in tracked:
                copies.append(p)
        elif (ctx.root / base).is_file():
            copies.append(p)
    if copies:
        tier = 2 if len(copies) > NUMBERED_TIER2 else 1
        ctx.add("numbered-copies", "landing safety", "local only", tier,
                f"{len(copies)} numbered copies of notes appeared beside the originals (a synced folder makes these)",
                "The nightly Vault Hygiene run sorts exact copies; nothing for you to do" if tier == 1 else TIER2_FIX,
                "System/Adding Your Computer.md", count=len(copies), paths=copies)
    label = synced_service(ctx.root)
    ctx.facts["synced_folder"] = label
    if label:
        ctx.add("synced-folder", "landing safety", "local only", 2, f"This vault sits inside {label}, a synced folder",
                "Move it out, step 2", "System/Adding Your Computer.md")


# ----------------------------------------------------------------------------- 8. connectors per routine

def bad_connectors(lines, connectors):
    """Connector names (from `connectors`) that a Routine health section reports missing, 404, or not connected."""
    bad = set()
    for line in lines:
        if routine_health.MISSING_OK_RE.search(line):
            continue
        m = re.search(r"\b(missing|not connected|absent|404|connector-missing)\b\s*:\s*(.*)$", line, re.I)
        clauses = [m.group(2)] if m else []
        clauses += [c for c in re.split(r"[,;]", line) if BAD_CONNECTOR_RE.search(c)]
        for c in clauses:
            for name in connectors:
                if re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", c, re.I):
                    bad.add(name)
    return bad


def check_connectors(ctx):
    notes = routine_health.daily_notes(ctx.root)[-14:]
    sections = [(d, routine_health.routine_health_lines(f)) for d, f in notes]
    for f in sorted((ctx.root / "System" / "routines").glob("*.md")):
        try:
            fm = check_keys.parse_frontmatter(f.read_text(encoding="utf-8", errors="replace")) if check_keys else None
        except Exception:
            fm = None
        if not isinstance(fm, dict):
            continue
        conns = fm.get("connectors") or []
        if not isinstance(conns, list):
            continue
        slug, title = fm.get("name") or f.stem, fm.get("title") or f.stem
        for c in conns:
            hits = [d for d, lines in sections if c in bad_connectors(lines, [c])]
            newest = bool(sections) and c in bad_connectors(sections[-1][1], [c])
            if newest or len(hits) >= 3:
                ctx.add(f"connector-missing:{slug}:{c}", "connectors", "blocks cloud", 2,
                        f"{title} cannot reach {c} ({n_of(len(hits), 'run')} in two weeks)",
                        f"Reconnect {c} under the routine's Connectors; your contact also gets a report", "System/Connecting Tools.md",
                        count=len(hits), first=min(hits).isoformat() if hits else None, last=max(hits).isoformat() if hits else None,
                        routine=slug, error_class="connector-missing")


# ----------------------------------------------------------------------------- output

def mask(value):
    if isinstance(value, str):
        return log_tool_use._mask(value) if log_tool_use else value
    if isinstance(value, list):
        return [mask(v) for v in value]
    if isinstance(value, dict):
        return {k: mask(v) for k, v in value.items()}
    return value


def sort_key(f):
    return (SEVERITIES.index(f["severity"]), SECTIONS.index(f["section"]) if f["section"] in SECTIONS else 99, -f["tier"], f["id"])


def summary_lines(findings, today):
    problems = [f for f in findings if f["severity"] != "fine"]
    errors = [f for f in findings if f["id"].startswith("check-error:")]  # fail open, but never hide an incomplete check
    visible = problems + errors
    if not visible:
        return ["1. Setup: no problems found; the next nightly run checks again (System/Who Decides.md)."]
    shown = visible[:6] if len(visible) <= 6 else visible[:5]
    lines = [f"{i}. {f['title']}. Fix: {f['fix']} ({f['page']})." for i, f in enumerate(shown, 1)]
    if len(visible) > 6:
        lines.append(f"6. {len(visible) - 5} more are listed for your contact in _generated/system-check/{today}.json (System/Who Decides.md).")
    elif len(lines) < 6 and not errors:
        lines.append(f"{len(lines) + 1}. Everything else checked out; the next nightly run confirms whether a fix held (System/Who Decides.md).")
    return [l.replace("..", ".") for l in lines]


def tier2_package(ctx, findings):
    alerts = read_json(ctx.root / "_generated" / "routine-alerts.json", {})
    alerts = alerts if isinstance(alerts, dict) else {}
    out = []
    for f in findings:
        if f["tier"] != 2 or f["severity"] == "fine":
            continue
        reason = "system-check:" + f["id"]
        last_sent = None
        try:
            last_sent = date.fromisoformat(str(alerts.get(reason))[:10])
        except ValueError:
            pass
        out.append({"reason": reason, "routine": f.get("routine") or "", "error_class": f.get("error_class") or f["id"].split(":")[0],
                    "count": f["count"], "first": f.get("first") or ctx.today.isoformat(), "last": f.get("last") or ctx.today.isoformat(),
                    "paths": f["paths"], "due": last_sent is None or (ctx.today - last_sent).days >= ALERT_DAYS})
    return out


def run(root, today, template):
    ctx = Ctx(root, today, template)
    for name, fn in (("configuration", check_configuration), ("needs a look", check_needs_a_look),
                     ("deterministic pieces", check_deterministic), ("routines and hooks", check_routines),
                     ("history", check_history), ("cloud brain", check_cloud_brain), ("landing safety", check_landing),
                     ("connectors", check_connectors)):
        try:
            fn(ctx)
        except Exception as e:
            ctx.add("check-error:" + name.replace(" ", "-"), name, "fine", 2, f"The {name} check could not run ({type(e).__name__})",
                    TIER2_FIX, "System/Who Decides.md", error_class=type(e).__name__)
    findings = sorted(ctx.findings, key=sort_key)
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    data = {"schema": "system-check/1", "date": today.isoformat(), "template": ctx.facts.pop("template", "not compared"),
            "problems": counts["blocks cloud"] + counts["local only"], "counts": counts, "findings": findings,
            "tier2_package": tier2_package(ctx, findings), "facts": ctx.facts, "summary": summary_lines(findings, today.isoformat())}
    return mask(data)


def markdown(data):
    n = data["problems"]
    status = f"Setup: {n} problem{'' if n == 1 else 's'}."
    errors = sum(1 for f in data["findings"] if f["id"].startswith("check-error:"))
    if errors:
        status += f" Incomplete: {n_of(errors, 'check')} could not run."
    return (f"# System check {data['date']}\n\n{status}\n\n" + "\n".join(data["summary"])
            + f"\n\nDetails for your contact (names and counts only): `_generated/system-check/{data['date']}.json`\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="How this vault is configured and whether it is working.")
    ap.add_argument("--vault", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    ap.add_argument("--template", default="")
    ap.add_argument("--today", default=os.environ.get("SYSTEM_CHECK_TODAY", ""))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    try:
        today = date.fromisoformat(args.today) if args.today else date.today()
    except ValueError:
        today = date.today()
    root = Path(args.vault).resolve()
    template = Path(args.template).resolve() if args.template and Path(args.template).is_dir() else None
    try:
        data = run(root, today, template)
    except Exception as e:  # fail open: a summary that says the check itself broke
        data = {"schema": "system-check/1", "date": today.isoformat(), "template": "not compared", "problems": 0,
                "counts": {s: 0 for s in SEVERITIES}, "findings": [], "tier2_package": [], "facts": {"error": type(e).__name__},
                "summary": [f"1. The system check could not run ({type(e).__name__}); the next nightly run tries again (System/Who Decides.md)."]}
    md = markdown(data)
    if not args.no_write:
        try:
            out = root / "_generated" / "system-check"
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{data['date']}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            (out / f"{data['date']}.md").write_text(md, encoding="utf-8")
        except Exception:
            pass
    print(json.dumps(data, indent=1, ensure_ascii=False) if args.json else md, end="" if not args.json else "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
