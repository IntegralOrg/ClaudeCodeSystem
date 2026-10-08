---
name: finish
description: Part 4 of 4 setup: demo the system with real data and learn to maximize it over time.
---

# Finish: Take It for a Spin and Learn to Maximize It

This is Part 4 of 4 in the setup process. The user has run `/onboard` (built vault), `/train` (learned the system), and `/connect` (connected tools). Now we demo the system with real data and teach them how to get the most value over time.

**Prerequisites:** Vault built, CLAUDE.md customized, tools connected and tested.

**Voice:** Encouraging, practical. This is the payoff -- show them what they built actually working.

**Important:** Use `AskUserQuestion` for every decision point. This step should feel like a victory lap, not more work.

---

## Step 1: Live Demo with Real Data

"Everything is set up. Let me show you what your system can actually do. I am going to pull real data from your tools right now."

### Calendar Check
Pull tomorrow's calendar (or today's if it is morning). Show the schedule:

"Here is what your calendar looks like for tomorrow:"
- List events with times, attendees, duration
- Flag any conflicts or back-to-back meetings
- Note protected deep work time

### Email Scan
If email is connected, surface the top 3-5 items needing attention:

"Here are the emails that probably need your attention:"
- List sender, subject, and a one-line summary
- Flag anything urgent

### Task Overview
If task manager is connected, pull current tasks:

"Here is what is open in your task manager:"
- List top tasks by priority
- Show what is due this week

### Meeting Prep (if applicable)
If they have a meeting coming up, prep it:

"You have a meeting with [Name] tomorrow at [time]. Here is what I found:"
- Recent context (transcript summary, open tasks for that client, last discussion points)
- Suggested talking points

Present all of this, then:

AskUserQuestion: "This is what your morning review will look like every day. How does it feel?"
Options:
- This is amazing, I can see how this saves time
- Cool but I want to adjust some things
- I have questions about how some of this works
- Can you show me something else?

---

## Step 2: Build Tomorrow's Plan

"Let me build your plan for tomorrow, just like the system will do automatically every night."

Generate a `Inbox/Today.md` for tomorrow based on:
- Calendar events
- Open tasks from inbox files
- Priority tiers from CLAUDE.md
- Their schedule preferences

Show them the result: "Open `Inbox/Today.md`. This is what you will see every morning."

AskUserQuestion: "Want to adjust anything in tomorrow's plan?"
Options:
- Looks good as is
- Move [task] to a different time block
- Add something I forgot
- Remove something

Make adjustments if requested.

---

## Step 3: Improvement Prompts

"The system gets better the more you use it. Here are things you can say to me anytime to improve how it works:"

### Adding Rules
"If I do something you do not like, tell me and I will add it as a rule. For example:"
- "Never schedule deep work after 4 PM"
- "Always put [Client] tasks before [Client] tasks"
- "When you write emails for me, keep them under 3 sentences"
- "Stop asking me about [thing], just do it"

"I will add these to your instruction manual (CLAUDE.md) so every future session follows them."

### Turning Tasks into Skills
"When we complete something that could be useful again, I will offer to turn it into a skill. You can also ask me directly:"
- "Turn this into a skill"
- "I want to do this every week"
- "Save this as a skill for client meeting prep"

"I will create a text file in `.claude/commands/` with the steps we used, and you can run it anytime with `/skill-name`. For example, if we just prepped for a client meeting together and it went well, I might say: 'This worked well. Want me to save this as a skill so you can run it before every client meeting?' Your system gets smarter every time you do this."

### Teaching Claude About Your Work
"The more context I have, the better I work. You can help by:"
- "Here is how [Client] likes their deliverables formatted..."
- "When I say 'urgent' for [Client], it means within 2 hours. For [Client], it means this week."
- "My team member [Name] handles [responsibility]. Loop them in on [type of task]."

### Fixing Mistakes
"When I get something wrong, the best fix is a rule, not just a correction:"
- Instead of: "No, put that in the other folder" (fixes it once)
- Say: "Always put [type of item] in [folder]. Add this to CLAUDE.md." (makes it far less likely to happen again)

AskUserQuestion: "Makes sense? Any rules you want to add right now based on what you have seen so far?"
Options:
- Yes, I want to add a few things
- No, I will add rules as they come up
- Can you give me more examples?

If they want to add rules, walk through each one and update CLAUDE.md together.

---

## Step 4: The Monthly Review

"Once a month, I will nudge you to do a system review. It takes about 15 minutes and keeps everything running smoothly."

Explain what the monthly review covers:
- **System feedback:** "I ask what is working and what is not"
- **Vault cleanup:** "I scan for stuck tasks, outdated notes, and things in wrong folders"
- **Testimonial scan:** "If you have Slack connected, I search for positive feedback from clients" (if applicable)
- **Improvement ideas:** "We discuss new features or workflows that would help"

"You do not have to remember to do this. I will mention it once at the start of a new month, and you can run it whenever it is convenient."

---

## Step 5: Power Tips

Share 3-4 tips based on their specific setup:

### If they have clients:
"You can ask me things like 'What is the status of [Client]?' and I will check their inbox file, recent transcripts, and task manager to give you a full picture."

### If they have meeting transcripts:
"After every call, your end-of-day routine pulls the transcript, extracts action items, and routes them to the right client file. You do not have to take notes during calls."

### If they have Slack:
"The end-of-day also scans your Slack DMs and mentions for anything you missed. Items that need action get routed to the right client file."

### For everyone:
"You can ask me anything about your system: 'What did I do last Tuesday?', 'What is pending for [Client]?', 'What meetings do I have this week?'. I have access to all your notes, calendar, and task history."

---

## Step 6: Wrap Up

"Your personal assistant system is fully set up and running. Here is the complete picture:"

```
Your system:
- Notes folder: [path]
- Instruction manual: CLAUDE.md (customized for you)
- Tools connected: [list with ✓]
- Skills: [list their skills]
- EOD routine: /eod (run before wrapping up each day)

Your daily rhythm:
- Morning: Open Today.md, run /morning (5 min)
- During the day: Ask Claude anything
- Evening: /eod runs automatically (or manually)

How to improve:
- Tell Claude when it gets something wrong
- Add rules to CLAUDE.md
- Turn successful tasks into skills
- Run /monthly-review once a month
```

AskUserQuestion: "You are all set. Anything else you want to adjust or ask about before we wrap up?"
Options:
- I am good, thanks!
- I want to change something
- One more question
- Can we do a practice run of /morning?

If they want a practice `/morning` run, do it right now with real data. This is the perfect way to end -- they see the full system working end to end.

---

## Step 7: Archive the Setup Files

"One last thing. The ClaudeCodeSystem folder you downloaded to set this up? You do not need it anymore for day-to-day use. Everything has been copied into your vault. But I am going to save a copy of the original setup files inside your vault, just in case you ever need to reference how things were originally configured."

**Action:** Archive the setup repo into the vault.

1. Create the archive folder: `Archive/ClaudeCodeSystem-Original/`
2. Copy the entire contents of the setup repo into it:
   - `docs/` (all reference documentation)
   - `Templates/`, `scripts/` and the root `CLAUDE.md` (the original template files)
   - `examples/` (automation scripts and settings)
   - `README.md`
   - `LICENSE`
3. Do NOT copy `.claude/commands/` (those are already installed at the vault root) or `.git/` (not needed).

4. After copying, update CLAUDE.md by adding this line to the Quick Reference table:

   `| Original setup files | Archive/ClaudeCodeSystem-Original/ (templates, examples, docs from initial setup) |`

5. Tell the user: "I saved a copy of the original setup files in your Archive folder. If your system ever drifts too far or you want to see how something was originally designed, you can find the original templates and documentation there. Your CLAUDE.md has a reference to it."

6. Now handle the original repo folder:

AskUserQuestion: "The original setup files are archived in your vault. Want me to clean up the download?"
Options:
- Yes, delete the original folder (it is saved in my vault now)
- Keep it for now, remind me later
- Keep both copies

**If delete:** Remove the ClaudeCodeSystem folder (or move to system trash). Tell them: "Cleaned up. The originals are safe in your vault at Archive/ClaudeCodeSystem-Original/."

**If remind later:** Add a task to `Inbox/[YourCompany].md` under Open Tasks:
`- [ ] Clean up the ClaudeCodeSystem download folder (originals are archived in vault)`

**If keep both:** Respect the choice, no further action.

---

**Final message:** "Welcome to your new system. Tomorrow morning, open `Inbox/Today.md`, and type `/morning`. I will be here."
