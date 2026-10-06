# Optimize -- Audit and Improve What You Already Have

Use this skill to evaluate your current tools, processes, or workflows and find opportunities to consolidate, simplify, or get more out of what you are already paying for.

**When to use:** You feel like you have too many tools, something is not working as well as it should, you are paying for features you do not use, or you want to streamline a process.

---

## Step 1: Pick the Focus

AskUserQuestion: "What do you want to optimize?"
Options:
- My tech stack (tools, subscriptions, integrations)
- A specific workflow or process
- How I spend my time
- A client's setup
- Something else

---

## Step 2: Current State Inventory

Based on their choice:

**If tech stack:**
- Read CLAUDE.md integrations section for currently connected tools
- Ask which services are configured (never open the credentials file; list the services named in CLAUDE.md)
- Ask: "Are there tools you pay for that are not listed here?"
- Build a table: Tool, Purpose, Monthly Cost (if known), How Often Used

**If workflow:**
- Ask them to describe the current process step by step
- Identify: manual steps, handoffs, bottlenecks, error-prone points
- Check if any existing tools or skills already cover parts of this

**If time:**
- Check time tracking data if available
- Ask about their typical day and where time feels wasted
- Review their daily schedule from CLAUDE.md

**If client setup:**
- Read the client's Company Profile
- Review their current tools and integrations
- Check for overlapping tools or underused features

Present the inventory: "Here is what I see: [summary]"

---

## Step 3: Analysis

Apply these filters:

### Overlap Detection
Are multiple tools doing the same job? List any overlaps with a recommendation on which to keep and which to drop. Prefer the tool that:
- Already has the most data or usage
- Integrates with other tools in the stack
- Costs less for equivalent functionality
- The team already knows how to use

### Underutilization Check
For each tool or process, rate utilization:
- **Heavy use** -- core to daily operations, worth the cost
- **Moderate use** -- used regularly but not critical, evaluate cost/benefit
- **Light use** -- rarely used, probably replaceable or removable
- **Unused** -- paying for something nobody touches, cut it

### Automation Candidates
Which manual steps could be automated with existing tools? Look for:
- Repetitive tasks done the same way every time
- Data entry or data transfer between systems
- Status updates or notifications that could be triggered automatically
- Reports or summaries generated manually

### Cost Recovery
What is the total monthly cost of tools that are light-use or unused? Can any be eliminated or downgraded to a cheaper tier?

---

## Step 4: Recommendations

Present findings as a prioritized list:

**Quick wins** (do this week):
- Things that save money or time immediately with minimal effort

**Medium-term improvements** (do this month):
- Consolidations, automations, or process changes that need some setup

**Strategic changes** (plan for next quarter):
- Larger shifts that require migration, training, or coordination

For each recommendation:
- What to change
- Expected benefit (time saved, cost reduced, quality improved)
- Effort required
- Any risks or dependencies

AskUserQuestion: "Which of these do you want to act on?"
Options:
- Start with the quick wins
- Let us tackle [specific item]
- Save this analysis and come back to it
- I have questions about [specific recommendation]

---

## Step 5: Execute and Record

For approved changes:
1. Execute what can be done right now (cancel a subscription, update a configuration, build a simple automation)
2. Create tasks in the inbox for items that need more work
3. Update CLAUDE.md if any integrations or tools changed
4. Note what was decided and why in the relevant project or client file

For items saved for later:
- Add to the relevant client file in `Inbox/`, or `Inbox/[YourCompany].md` if cross-client, with a target date
- Include the analysis so you do not have to redo it
