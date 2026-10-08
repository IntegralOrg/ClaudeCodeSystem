#!/usr/bin/env python3
"""SessionStart: warn, every session, when the vault sits inside a cloud-synced folder.
Two syncers on one folder (iCloud/OneDrive/Dropbox/Drive plus git) produce conflict copies and can
corrupt .git; background scripts also lose file access there. Fails open."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import project_dir, run  # noqa: E402

SYNCED_FOLDER_MARKERS = (
    ("com~apple~CloudDocs", "iCloud"), ("Mobile Documents", "iCloud"), ("iCloud", "iCloud"),
    ("OneDrive", "OneDrive"), ("Dropbox", "Dropbox"),
    ("Google Drive", "Google Drive"), ("GoogleDrive", "Google Drive"), ("CloudStorage", "a cloud-storage"),
)


def synced_service(path):
    parts = [p.lower() for p in Path(path).resolve().parts]
    for marker, label in SYNCED_FOLDER_MARKERS:
        if any(marker.lower() in part for part in parts):
            return label
    return None


def main(payload):
    label = synced_service(project_dir(payload))
    if not label:
        return
    text = (f"WARNING: this vault is inside {label}, a synced folder. Git and the sync service will fight over the same "
            "files (conflict copies, a corrupted .git, scripts that cannot read the folder). Fix, before anything else: "
            "close this folder, move it to ~/Brain (Windows: %USERPROFILE%\\Brain) or clone it there again with GitHub Desktop, "
            "and open the new location in Claude Desktop. Say this to the user first, in those words, every session until it is fixed.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))


if __name__ == "__main__":
    run(main)
