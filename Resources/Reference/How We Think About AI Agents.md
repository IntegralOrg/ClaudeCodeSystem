# How We Think About AI Agents

*From Integral -- the team behind your system.*

This document captures the philosophy and principles behind how your AI assistant was built. These ideas inform every skill, every workflow, and every design decision in your system. As you work with your agent, refer back to these concepts. They will help you get more out of the system and understand why things work the way they do.

---

## The Big Idea: Context Engineering

Most people focus on how to write better prompts. That matters, but the real leverage is in **context engineering**: giving your agent the right information, in the right place, at the right time.

A prompt is what you say in the moment. Context is everything your agent already knows before you say anything: your preferences, your clients, your schedule, your past work, your brand voice, your SOPs. When context is strong, prompting becomes simple. You stop explaining and start directing.

**Without context** (a regular chat window): your agent is smart but uninformed. You re-explain everything. You correct constantly. Output quality: maybe 50-60%.

**With engineered context** (your vault, your CLAUDE.md, your skills): your agent knows who you are, how you work, and what you expect. Output quality: 80-95%. The gap between those two numbers is hours of your time every week.

Your vault is the engine of context engineering. Every file you add, every preference you record, every skill you build improves the baseline. It will not be perfect. But the gap between "good enough" and "needs fixing" shrinks over time.

---

## The Proficiency Ladder

There are distinct levels of AI proficiency. Knowing where you are helps you know what to work toward.

**Level 0: Not using AI.**
You do everything manually.

**Level 1: Basic chat.**
You use AI for one-off tasks: drafting an email, answering a question, generating some text. Each conversation starts from zero.

**Level 2: Engineered context.**
Your agent reads your vault. It knows your clients, your calendar, your to-do list. It takes informed actions without you re-explaining everything. This is where the system starts working *for* you instead of just *with* you.

**Level 3: Skills and automation.**
You have pre-built workflows. Instead of writing detailed prompts, you type `/eod` or `/morning` and the agent follows a proven process. The quality is consistent because the process is defined.

**Level 4: Scheduled automation.**
Your skills run on a schedule. The end-of-day routine fires automatically. The morning brief is waiting when you open your laptop. You are not triggering anything manually.

**Level 5+: Self-monitoring.**
The agent checks its own quality, flags issues, runs validation. It improves itself by learning from corrections and patterns.

**Most people think they are at Level 1 or 2. The breakthrough happens between Levels 2 and 3.** That is where your system is designed to take you.

---

## Your Agent Is a New Hire

Think of your AI assistant like the smartest person you have ever worked with, starting their first day at your company. They are capable of extraordinary work, but without proper context and direction, they will not perform the way you want.

**The first two weeks are training.** You will correct things. You will say "not like that, like this." That is normal and expected. Corrections get recorded in your instruction manual (CLAUDE.md) or memory files, which raises the floor. The agent will still make mistakes, but the frequency and severity drop as context builds up.

**Tell it what was wrong, what you want instead, and make it stick.** Do not just fix the output. Add a rule:
- Instead of: "No, put that in the other folder" (fixes it once)
- Say: "Always put client tasks in the client's Inbox file. Add this to CLAUDE.md." (makes it far less likely to happen again)

**Give examples, not just rules.** AI performs significantly better with examples. Do not say "write like me." Show it 10 emails you have written. Show it posts you like and posts you do not. Concrete examples beat abstract descriptions every time.

**The compounding effect is real.** If you invest 10-15 minutes a day giving feedback, the improvement compounds. Within a few weeks, the agent handles tasks you used to spend hours on. Within a month, it feels like a different tool entirely.

---

## Progressive Trust

Do not give your agent full access to everything on day one. Build trust the way you would with any new team member.

**Week 1-2: Read-only mode.** The agent researches, drafts, and recommends. You review and execute. This is the learning period for both of you.

**Week 3-4: Low-risk writes.** Allow the agent to create tasks, draft emails (for your review), update notes. Things that are easy to undo.

**Month 2+: Higher-risk writes.** After a consistent track record, extend access to more systems. The agent has proven it understands your preferences.

**The reversibility test:** Before allowing any action, ask: if the agent does this wrong, can I undo it? If yes, it is probably safe to allow. If no, keep a human in the loop.

---

## When to Use AI vs. Traditional Code

AI is not the right tool for everything. Knowing the difference saves time and prevents frustration.

**Use your AI agent when:**
- The task requires judgment, analysis, or creativity
- The input is unstructured (emails, transcripts, documents, conversations)
- The task varies each time (different clients, different contexts)
- You need to bridge multiple systems that do not talk to each other
- Perfect consistency is not critical

**Use traditional automation when:**
- The task is exactly the same every time
- Perfect consistency is required (financial data, invoicing, compliance)
- The logic is purely conditional (if X then Y, no judgment needed)
- The data is structured and predictable

The best systems combine both. Your agent handles the thinking. Traditional code handles the mechanical parts.

---

## Skills: Your Repeatable Workflows

A skill is a task you have done successfully that gets saved as a repeatable routine. Every skill is a text file with instructions your agent follows step by step.

**How skills grow:**
1. You do a task with your agent for the first time
2. It works well
3. You (or your agent) save the process as a skill
4. Next time, you type one command and the whole thing runs

**Do not pre-build skills speculatively.** Let them emerge from real work. The skills that stick are the ones born from tasks you actually repeat.

**Good skills share common traits:**
- They pull relevant context automatically (you do not re-explain)
- They ask clarifying questions before executing
- They follow a consistent process
- They are easy to update when your preferences change

As your skills library grows, your system becomes increasingly autonomous. Tasks that took 30 minutes become 5-minute reviews of work your agent already completed.

---

## The Daily Loop

Your system is designed around a daily rhythm that replaces the 30-60 minutes you already spend organizing, planning, and chasing loose ends.

**End of day:** Run your EOD routine before wrapping up. Your agent processes calls, emails, messages, and tasks. It extracts action items, routes them to the right places, and builds tomorrow's plan. You can walk away while it runs.

**Morning:** Read your daily plan. Run your morning review. Confirm priorities in 3-5 minutes, not 30. The plan was already built last night.

**During the day:** Use your agent for anything: draft emails, research, create documents, prep for meetings, manage tasks. The more you use it, the more context it has, the better it gets.

**The key insight:** the morning should be confirmation, not creation. If you are spending 30 minutes planning your day every morning, the system is not doing its job.

---

## Working Async

You are not supposed to sit and watch your agent work. These are tools for parallel productivity.

**Run multiple tasks at once.** Open several conversations. One researches, another writes, another organizes. Check in when they need input.

**Quality control for important work:** If something is client-facing or high-stakes, get a second opinion. Open another conversation and ask it to review the first agent's output. Two perspectives catch more issues than one.

**Let the agent tell you when it needs you.** If it has a question, it will ask. If it needs approval, it will pause. You do not need to babysit. Check in periodically, approve what looks right, course-correct what does not.

---

## Common Mistakes to Avoid

**Expecting everything to work perfectly from day one.** The system improves with use. The first week is training. Give it time and feedback.

**Not giving feedback.** Using the agent like a vending machine. If you never tell it what you liked or did not like, it cannot improve. Feedback is the fuel.

**Bloating your instruction manual.** CLAUDE.md is read every session. Keep it focused: preferences, pointers, guidelines. Move detailed SOPs and reference material into separate files that get read on demand.

**Chasing flashy setups you do not understand.** Social media is full of impressive agent demos. Most skip the hard parts: security, reliability, memory management. Build what you need, not what looks cool.

**Trying to automate everything at once.** Start with one workflow. Get it working well. Then expand. Trying to automate five things simultaneously means none of them work reliably.

---

## The System Improves Every Time You Use It

This is not a static tool. It is a system that gets better every week:

- When the agent makes a mistake, add a guideline to CLAUDE.md
- When you repeat something manually, turn it into a skill
- When you learn a quirk about a tool or workflow, save it to memory
- Run a monthly review to clean up, reorganize, and upgrade

The people who get the most out of this system are not the most technical. They are the ones who consistently give feedback and let the system compound. Fifteen minutes of feedback today saves hours next month.

---

*This document is maintained by Integral. As the system evolves, updated versions will be delivered through the Integral platform.*
