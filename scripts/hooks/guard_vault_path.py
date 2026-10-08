#!/usr/bin/env python3
"""SessionStart: warn, every session, when the vault sits inside a cloud-synced folder.
Two syncers on one folder (iCloud/OneDrive/Dropbox/Drive plus git) produce conflict copies and can
corrupt .git; background scripts also lose file access there. Fails open."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import project_dir, run  # noqa: E402

# Whole path components only (case-insensitive), so "icloud-tools" or a user named "dropboxfan" never match.
SYNCED_EXACT = (
    ("com~apple~clouddocs", "iCloud"), ("mobile documents", "iCloud"), ("icloud", "iCloud"), ("iclouddrive", "iCloud"),
    ("onedrive", "OneDrive"), ("dropbox", "Dropbox"), ("cloudstorage", "a cloud-storage"),
)
SYNCED_PREFIX = (
    ("onedrive-", "OneDrive"), ("onedrive -", "OneDrive"),
    ("googledrive-", "Google Drive"), ("google drive", "Google Drive"),
    ("dropbox (", "Dropbox"), ("onedrive for", "OneDrive"),
)


def synced_service(path):
    parts = [p.lower() for p in Path(path).resolve().parts]
    for part in parts:  # service-specific prefixes first: .../CloudStorage/GoogleDrive-x is Google Drive, not generic
        for prefix, label in SYNCED_PREFIX:
            if part.startswith(prefix):
                return label
    for part in parts:
        for marker, label in SYNCED_EXACT:
            if part == marker:
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
