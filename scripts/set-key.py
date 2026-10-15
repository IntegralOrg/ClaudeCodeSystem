#!/usr/bin/env python3
"""Ask the person for one key in a hidden-input pop-up and save it to the credentials file.

The value goes from the pop-up straight into the vault's credentials file (the one
envload.py reads). It is never printed, logged, or passed on a command line, so it
never reaches the chat or the session transcript. Output is the key's NAME only.

  python3 scripts/set-key.py FATHOM_API_KEY [--label "Fathom API key"] [--json]

macOS: a native dialog with a hidden answer box. Windows: a masked WinForms box.
Elsewhere: a hidden terminal prompt (getpass) when a terminal is attached.

Stdout first token: SAVED, CANCELLED, EMPTY, BAD_NAME, NO_PROMPT, FAILED.
Exit: 0 saved, 1 failed, 3 cancelled or empty (ask the person again or move on).

Test hook: SET_KEY_FAKE_VALUE is the value the dialog would return
("__CANCEL__" means cancel), so tests never open a dialog.
"""
import argparse
import getpass
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from envload import find_root  # noqa: E402

NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
DIALOG_TIMEOUT = 300

WIN_FORM = r'''
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object System.Windows.Forms.Form
$f.Text = "Brain: add a key"; $f.Width = 520; $f.Height = 190; $f.StartPosition = "CenterScreen"; $f.TopMost = $true
$l = New-Object System.Windows.Forms.Label; $l.Text = $env:SET_KEY_PROMPT; $l.Left = 12; $l.Top = 12; $l.Width = 480; $l.Height = 48
$t = New-Object System.Windows.Forms.TextBox; $t.Left = 12; $t.Top = 66; $t.Width = 480; $t.UseSystemPasswordChar = $true
$ok = New-Object System.Windows.Forms.Button; $ok.Text = "Save"; $ok.Left = 400; $ok.Top = 104; $ok.DialogResult = "OK"
$c = New-Object System.Windows.Forms.Button; $c.Text = "Cancel"; $c.Left = 310; $c.Top = 104; $c.DialogResult = "Cancel"
$f.Controls.AddRange(@($l, $t, $ok, $c)); $f.AcceptButton = $ok; $f.CancelButton = $c
if ($f.ShowDialog() -eq "OK") { [Console]::Out.Write($t.Text) } else { exit 1 }
'''


def say(token, name, as_json, code):
    if as_json:
        print(json.dumps({"result": token, "name": name}))
    else:
        print(f"{token} {name}")
    sys.exit(code)


def prompt_text(label):
    return f"Paste your {label}, then click Save. It is saved on this computer; Claude never sees it."


def ask_fake():
    v = os.environ.get("SET_KEY_FAKE_VALUE")
    if v is None:
        return False
    return None if v == "__CANCEL__" else v


def ask_mac(label):
    script = (
        'tell application "System Events"\n'
        "  activate\n"
        f"  set r to display dialog {json.dumps(prompt_text(label), ensure_ascii=False)} default answer \"\" with hidden answer "
        f'with title "Brain: add a key" buttons {{"Cancel", "Save"}} default button "Save" '
        f"cancel button \"Cancel\" giving up after {DIALOG_TIMEOUT}\n"
        "  if gave up of r then return \"\"\n"
        "  return text returned of r\n"
        "end tell"
    )
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=DIALOG_TIMEOUT + 30)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0:
        return None  # Cancel (osascript error -128) or no dialog at all
    return r.stdout.rstrip("\n")


def ask_windows(label):
    env = dict(os.environ, SET_KEY_PROMPT=prompt_text(label))
    try:
        r = subprocess.run(
            ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-Command", WIN_FORM],
            capture_output=True, text=True, env=env, timeout=DIALOG_TIMEOUT + 30,
        )
    except subprocess.TimeoutExpired:
        return None
    except OSError:
        return False
    return None if r.returncode != 0 else r.stdout


def ask_terminal(label):
    if not sys.stdin.isatty():
        return False
    try:
        return getpass.getpass(f"Paste your {label} (hidden), then press Enter: ")
    except (EOFError, KeyboardInterrupt):
        return None


def clean(value):
    value = value.strip()
    # People paste with the decoration the instructions showed: quotes, brackets, a leading NAME=.
    for left, right in (('"', '"'), ("'", "'"), ("<", ">"), ("[", "]"), ("{", "}")):
        if len(value) >= 2 and value[0] == left and value[-1] == right:
            value = value[1:-1].strip()
    return value


def save(path, name, value):
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    pattern = re.compile(rf"^\s*(export\s+)?{re.escape(name)}\s*=")
    replaced = False
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{name}={value}"
            replaced = True
    if not replaced:
        lines.append(f"{name}={value}")
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".setkey-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass  # Windows: permissions are inherited from the folder
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def vault_root():
    start = os.environ.get("CLAUDE_PROJECT_DIR")
    return find_root(start) if start else find_root()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("name", help="the key's name, e.g. FATHOM_API_KEY")
    p.add_argument("--label", help="what the pop-up calls it (default: the name)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    a = p.parse_args()

    if not NAME_RE.match(a.name):
        say("BAD_NAME", a.name, a.json, 1)
    label = a.label or a.name

    value = ask_fake()
    if value is False:
        system = platform.system()
        if system == "Darwin":
            value = ask_mac(label)
        elif system == "Windows":
            value = ask_windows(label)
        else:
            value = ask_terminal(label)
    if value is False:
        say("NO_PROMPT", a.name, a.json, 1)
    if value is None:
        say("CANCELLED", a.name, a.json, 3)
    value = clean(value)
    m = re.match(rf"^(?:export\s+)?{re.escape(a.name)}\s*=\s*", value)
    if m:
        value = clean(value[m.end():])
    if not value or "\n" in value or "\r" in value:
        say("EMPTY", a.name, a.json, 3)

    try:
        save(vault_root() / ".env", a.name, value)
    except (OSError, ValueError):
        say("FAILED", a.name, a.json, 1)
    say("SAVED", a.name, a.json, 0)


if __name__ == "__main__":
    main()
