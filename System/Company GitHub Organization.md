---
type: reference
created: 2026-10-13
updated: 2026-10-13
---
# Company GitHub Organization

**What it is.** A vault is a private Git repository on GitHub. It can live on the person's own GitHub account, or in a GitHub organization the company owns. The system works the same way in both: the automatic saving to `main`, the cloud routines, and `/update` only ever talk to the repository named `origin`, wherever it is.

**Our recommendation.** When the company pays for the Claude seat, the vault lives in the company's organization. A vault holds company work (orders, customer mail, numbers), the company can keep it when someone changes roles or leaves, and the organization's owners can open it when they need to, the same way an email administrator can open a mailbox. On a personal account none of that is possible. A person who pays for their own seat keeps the vault on their own account.

Say the plain version to each person before their vault is created: in the organization, the vault is company property, nobody reads it as a matter of course, and the organization's owners can. Setup asks each person where the vault should live only when their GitHub account belongs to an organization; a prepared brief can answer for them (`github owner: <organization>`).

## Setting up the organization (an owner does this once)

Fifteen minutes, before the first person's setup. Every item below is in the organization's **Settings** on github.com.

1. **Plan.** The Team plan (paid, per member) gives you the member controls below; the Free plan lacks some of them.
2. **Owners.** Exactly two. Owners can open every repository in the organization, so keep the list short and known.
3. **Two-factor authentication required** for every member (Settings, Authentication security).
4. **Base permission: No permission** (Settings, Member privileges). Each person is then given **Admin** on their own vault repository and sees nothing else. Admin, not Write, so they can install the Claude GitHub app on it themselves.
5. **Members cannot create public repositories**, and **forking of private repositories is off** (same page).
6. **Third-party access.** If "OAuth app access restrictions" is on, approve the **GitHub CLI** application. The system saves through the GitHub CLI's sign-in; an unapproved CLI makes every save fail quietly on every member's computer.
7. **Install the Claude GitHub app** on the organization (`github.com/apps/claude`) with "Only select repositories", and add each vault repository as it is created. A member who is not an owner can only request the install; approve the request when GitHub emails it.
8. **No branch protection or rulesets on vault repositories.** The system saves straight to `main` after every session. A rule that requires a pull request, a review, or a status check stops every save.

Repositories are named `brain-<GitHub username>`, one per person. Setup creates each one (`connect --owner <organization>`), or reuses an empty private repository an owner created under that name.

## Moving an existing vault into the organization

For a vault that started on a personal account. GitHub keeps a redirect from the old address, so nothing breaks on the day of the move, but finish every step.

1. **Before the transfer**, the person's agent checks the repository history for anything that should not become visible to the organization's owners: `git log -p | grep -n -i -E 'api[_-]?key|secret|token|password'` from the vault. A hit is handled before the move (the key is rotated at the tool that issued it; the file is fixed).
2. **Transfer.** On github.com, in the repository's Settings, Danger Zone, **Transfer ownership** to the organization, naming it `brain-<username>`. An owner accepts the transfer, then gives the person **Admin** on it.
3. **On each of the person's computers**, the agent runs `python3 scripts/setup/github.py retarget --to <organization>/brain-<username>`: it confirms the new home is private, points `origin` at it, and proves it is reachable (`RETARGETED`). Then `bash scripts/land-local.sh --final` and the last line of `_generated/landing.log` reads "landed on main" or "nothing to push".
4. **Cloud.** Add the repository to the Claude GitHub app's installation on the organization (item 7 above), then in the person's Claude cloud environment choose the repository under the organization, and run one routine by hand (`System/Routines.md`, "If a routine is stale or not live"). A routine still pointed at the old address runs in an empty container.
5. The old repository no longer exists; nothing to delete.

## When someone leaves

Remove them from the organization. The repository stays, with the owners able to open it; assign it to whoever takes the work over, or archive it. Their computer's copy can no longer save to it, and their cloud routines stop at the next run.

## What changes for the agent

Nothing in daily work. `land-local.sh`, `cloud-land.sh`, and the hooks use only `origin`. The organization matters at setup (`System/Setup Procedure.md`, B3 and B4), when adding a computer (`System/Adding Your Computer.md`, the clone's name), and at the move above.
