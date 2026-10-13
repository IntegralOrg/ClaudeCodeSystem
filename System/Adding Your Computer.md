---
type: reference
created: 2026-10-08
updated: 2026-10-13
---
# Adding Your Computer

If you started on your computer (you downloaded the system and opened it in Claude Desktop), this is already done: setup put your vault in `~/Brain` and connected it to GitHub. This page is for a vault that started in a cloud session.

**What it is.** The system already works in a cloud session (nothing installed). Adding your computer puts a second copy of the vault on your machine so you can work on it in Claude Desktop, with the same files, the same rules, and the same automatic saving to `main`.

**Our recommendation.** Do it once, on the machine you work at most. Another machine is another clone, done the same way; your phone is the cloud session, which needs nothing installed.

**The steps.** In this order.

## 1. Install Claude Desktop

Download Claude Desktop from claude.com/download and sign in with your Claude account.

- **Windows, before anything else:** turn on **Developer Mode** (Settings, System, For developers); install **Git for Windows** (git-scm.com); install **Python 3 from the Microsoft Store** (it provides the `python3` command the hooks call; the python.org installer does not provide `python3` unless you add it yourself, and without it every hook is silently absent); enable **Virtual Machine Platform** (Windows Features); then restart once.
- **Mac:** open Terminal and run `xcode-select --install` first, and accept the prompt (it installs Git). The screen permissions come later, with the agent: in your first session on this computer it asks macOS for them, which shows the prompts and opens System Settings, and you switch on **Claude Code** under **Accessibility** and under **Screen Recording**. It is listed as Claude Code, not Claude, because Claude Desktop runs each session through that helper app. Then start a new session so the grants take effect. The first time the agent drives the screen, macOS asks once whether Claude Code may control **System Events**: click OK.

## 2. Install GitHub Desktop and clone the vault

1. Install **GitHub Desktop** (desktop.github.com). Sign in with the browser when it asks.
2. Clone your vault repository (`brain` on your own account, or `brain-<your username>` in your company's organization; see `System/Company GitHub Organization.md`) to `~/Brain` (on Windows, `%USERPROFILE%\Brain`). GitHub Desktop's default clone location, `~/Documents/GitHub`, may be iCloud-synced when "Desktop & Documents" sync is on, so choose `~/Brain` yourself.

> **Never clone it inside iCloud, OneDrive, Dropbox, or Google Drive.** Two syncers on one folder (the cloud drive and Git) produce conflict copies and can corrupt the repository. The vault warns at the start of every session until it is moved out of a synced folder.

## 3. Open the folder in Claude Desktop

Open the folder: in Claude Desktop choose **File, Open folder** and pick `~/Brain`. Start a session there. If Claude Desktop offers to run the session in a worktree for this folder, decline: landing only runs on `main`.

## 4. What the agent does in that first local session

Without asking you between steps, the agent:

1. Runs `git --version` and `python3 --version` to confirm both exist (and tells you what to install if one is missing). On Windows it also runs `python3 -c "print(1)"`; if that fails, it repeats the Microsoft Store Python 3 instruction from step 1.
2. Runs `python3 scripts/check-keys.py --init`, which creates the credentials file with blank values, and walks you through the keys: for each missing name it tells you what it is for and where to get it, and you paste the value yourself into the file, opened in Claude Desktop's file pane. The file is `.env` at the vault root and it is hidden: in the file pane turn on hidden files, or on a Mac press Command+Shift+Period in the Open dialog. Values never go in the chat. See `System/Connecting Tools.md`.
3. Checks that this computer can reach GitHub from the command line: it runs `GIT_TERMINAL_PROMPT=0 git ls-remote origin` in the vault. If that fails, GitHub Desktop's sign-in is not visible to command-line Git, so the agent has you install **Git Credential Manager** (a download with a link, browser sign-in, no terminal) and retries; if it still fails, the last resort is `gh auth login --web && gh auth setup-git`. Then it runs `bash scripts/land-local.sh --final` and confirms the last line of `_generated/landing.log` is "landed on main" or "nothing to push".
4. Offers to drive the screen for anything that is click-through (a connector page, a settings screen). It only starts when you say yes in that session. Before the first drive it runs the skill's check (`screenctl.py doctor`) while you are still at the keyboard; if a permission is missing it runs `screenctl.py request` and tells you exactly which switch to turn on. Any missing permission, and the one-time System Events prompt, shows up then rather than halfway through a task. When a drive ends, it brings you back to the Claude window with a sound; if you took the machine back yourself, it leaves you where you are and sends a notification instead.
5. Runs `bash scripts/system-journal/install.sh --vault ~/Brain --write-hooks`. This is the only global write the system makes: it adds three hooks to `~/.claude/settings.json` and copies scripts to `~/scripts/system-journal/`. The end-of-session distill step runs `claude -p`, which is a paid call against your Claude account. (Skip this step if you do not want that; the vault works without it.)
6. Installs the **Superpowers** plugin without asking, and says in one sentence what it is ("Superpowers adds the planning, brainstorming, and debugging skills I use on bigger jobs"). It runs `claude plugin marketplace add obra/superpowers-marketplace` and then `claude plugin install superpowers@superpowers-marketplace` from the session; if the `claude` command is not available in this session, it opens Settings, Plugins and installs it there, driving the screen if you have said yes to that (see "Claude plugins" in `System/Connecting Tools.md`).
7. Lists the connectors this session can see, and tells you which are missing.
8. Offers **Wispr Flow** by name, once ("Many people talk to this system rather than type. Wispr Flow turns speech into text anywhere on your computer. Want me to install it?"), and on yes drives the install from wisprflow.ai with the drive-screen skill. On no, it never asks again.

## 5. Optional: voice input

**Wispr Flow** turns speech into typed text anywhere on your computer, which suits talking to Claude. The agent offers it once in your first local session (step 4 above); you can also install it any time from wisprflow.ai.

## What changes afterwards

You can work in Claude Desktop on your own machine. Each time Claude finishes a turn, `scripts/land-local.sh` commits and puts the work on `main`, so the cloud routines and your other devices see it. A local session also pulls the latest from GitHub when it starts (fast-forward only, never over your unsaved edits). If saving ever fails, the next session opens with a note saying so (see `System/How This Works.md`).
