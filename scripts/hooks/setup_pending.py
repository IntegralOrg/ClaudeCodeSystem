#!/usr/bin/env python3
"""SessionStart: if the vault has not been set up yet, tell the agent to start setup now.
The only signal is the SETUP_PENDING file at the vault root; setup deletes it right after writing the completion line, before landing.
Silent in the template repository itself (maintainers are not clients). Fails open."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import is_template_repo, project_dir, run  # noqa: E402

MARKER = "SETUP_PENDING"
PROCEDURE = Path("System") / "Setup Procedure.md"


def main(payload):
    root = Path(project_dir(payload))
    if not (root / MARKER).is_file() or is_template_repo(root):
        return
    if (root / PROCEDURE).is_file():
        text = ("This vault is not set up. Read `System/Setup Procedure.md` now and begin setup in this session; "
                "do not wait for a command and do not ask whether to start. Setup deletes the "
                f"`{MARKER}` file at the vault root right after writing its completion line. "
                "If no human is present in this session (a scheduled routine), do not run setup; report that setup is pending.")
    else:
        text = (f"This vault is not set up (`{MARKER}` exists) but `System/Setup Procedure.md` is missing. "
                "Tell the user the template is incomplete and to re-create the repository from the template.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))


if __name__ == "__main__":
    run(main)
