---
name: jira-ticket
description: Create a SAAS Jira ticket. Just describe what you're working on and it handles the rest.
argument-hint: <describe the work>
---

# Create Jira Ticket

Create a ticket in the SAAS project with smart defaults so the developer can just describe the work in plain English.

## Input

`$ARGUMENTS` — A free-form description of the work. Can be as brief as a title or as detailed as needed. Examples:
- `/jira-ticket fix the login redirect bug`
- `/jira-ticket refactor the pillow processor to reduce memory usage`
- `/jira-ticket investigate formplayer memory spikes, assign to Graham`
- `/jira-ticket Delete FF follow-up: remove old SMS settings model, hours`
- `/jira-ticket update exports page header, assign to Daniel, P3`
- `/jira-ticket add case search filter, in the ERM epic, hours`
- `/jira-ticket Subtask 1: add geolocation to formplayer, under SAAS-18500`

## Defaults & Constants

- **Project:** `SAAS` (always)
- **Cloud ID:** `dbff467f-3c3f-4ced-a2ba-a29e1941edd6`
- **Effort Range field:** `customfield_10160`
- **Sprint field:** `customfield_10010`

## Assignee (Dynamic)

The assignee is determined from the input using natural language:

1. **If the user mentions someone by name** (e.g., "assign to Daniel", "for Graham", "Ahmad should do this", "give this to Evan"), use `lookupJiraAccountId` to search for that person's name and use their `accountId`.
2. **If no one is mentioned**, assign to self — use `atlassianUserInfo` to get the current authenticated user's account ID. Developers self-assign 94% of the time.
3. **If the user explicitly says "unassigned"**, do not set `assignee_account_id`.

Never hardcode an assignee ID. Always resolve dynamically.

## Issue Type Detection

Infer the issue type from the description using natural language. The user does NOT need to use exact keywords — understand intent.

**Based on dev team patterns:** Task is overwhelmingly dominant (88% of IC dev tickets). Improvement is a distant second. Bug and Story are rare. The team does not use the `Feature`, `Design`, or `New Feature` issue types.

| Issue Type | Exact Jira Name | When to Use |
|---|---|---|
| Task | `Task` | **Default for almost everything.** New functionality, creating things, investigations, follow-ups, migrations, deletions, management commands, specs, testing, FF cleanup, hotfixes. If "add", "new", "create", "implement", "build", "investigate", "delete", "set up", "test", "remove", "merge", "track", "confirm", "validate", "spec" — use Task. |
| Improvement | `Improvement` | Enhancing something that **already works** and the user explicitly frames it as an improvement: "improve", "refactor", "optimize", "clean up", "enhance", "modernize", "simplify", "consolidate", "better error message", "disable when already", "replace X with Y". Only use this when the intent is clearly about making an existing thing better, not building something new. |
| Bug | `Bug` | Something is **broken or wrong** and the user explicitly says so: "bug", "broken", "crash", "error", "fails", "regression", "not working". Devs rarely file bugs (3% of tickets) — most bug tickets come from support. |
| Performance/Scale | `Performance/Scale` | Infrastructure performance issues: "slow", "performance", "memory spikes", "latency", "OOM", "bottleneck", "connection spikes", "apdex". |
| Story | `Story` | User stories, research spikes, ideation, UX research. Very rarely used. |

**Important:** Use the exact Jira name from the second column when calling `createJiraIssue`. When in doubt, use `Task`.

## Summary Style

The team writes summaries in a consistent style. Follow these conventions:

1. **Sentence case** — NOT Title Case. Write "Investigate formplayer memory usage" not "Investigate Formplayer Memory Usage".
2. **Verb-first** when possible — The most common starting verbs on the team are: Create, Delete, Investigate, Test, Remove, Track, Confirm, Validate, Merge, Accept, Separate, Downsize.
3. **Keep it under 80 characters** — concise but descriptive. Median is 55 chars.
4. **Preserve user prefixes** — If the user includes a prefix pattern, keep it exactly as-is. Common team patterns:
   - `Delete FF: ...` (feature flag removal — most common pattern)
   - `Delete FF follow-up: ...` (post-deletion cleanup)
   - `GA FF: ...` (GA feature flag work)
   - `User & Security Features: ...` (feature audit)
   - `Data & Export Features: ...` (feature audit)
   - `Subtask N: ...` (numbered subtasks)
   - `Onboarding: ...` (onboarding tasks)
   - `[Investigation] ...` or `[Mobile] ...` (bracket tags)
   - `Hotfix X.Y.Z - ...` (hotfix tasks)
5. **Strip metadata from summary** — Remove effort, priority, assignee, and epic references. The summary should only contain the work description.

## Effort Range

The **Effort Range** (`customfield_10160`) is required. Infer from natural language in the input:

| Value | Jira Option ID | Trigger Signals |
|---|---|---|
| Hours | `10384` | "hours", "hour", "quick", "small", "a few hours", "half day", "simple" |
| Days | `10385` | "days", "day", "a day or two", "multi-day", "several days", "large" |
| Too Large - Needs Breaking Down | `11973` | "too large", "needs breaking down", "epic-sized", "needs to be split", "way too big" |
| Awaiting Score | `10383` | "not sure", "unsure", "unknown effort", "TBD", "awaiting score" |
| N/A | `10426` | "n/a", "not applicable" |

**Default when no effort is mentioned:** Use `Hours` (id: `10384`). This matches 62-79% of dev-created tickets. Only ask the user if the work sounds like it could be multi-day or ambiguous.

## Priority Detection

Detect priority from the input using natural language. If no priority is mentioned, **do not set it** — the Jira default is P6 and developers almost never override this (88-98% leave it at P6). Only set priority when the user explicitly mentions it.

| Priority | Jira ID | Trigger Signals |
|---|---|---|
| P1 | `1` | "P1", "blocker", "site down", "production down", "outage", "SEV1", "sev-1" |
| P2 | `2` | "P2", "urgent", "ASAP", "critical", "SEV2", "drop everything" |
| P3 | `3` | "P3", "high priority", "important", "soon" |
| P4 | `4` | "P4", "normal priority", "medium priority" |
| P5 | `5` | "P5", "low priority", "when you get a chance", "not urgent" |
| P6 | `10000` | "P6" (rarely set explicitly — it's the default) |
| P7 | `10001` | "P7", "someday", "lowest" |

Set priority via `additional_fields`: `"priority": {"id": "<priority_id>"}`

## Epic Linking

If the user mentions an epic, link the new ticket as a child of that epic using the `parent` field on `createJiraIssue`.

**Team patterns:** Developers link to a parent epic ~80-100% of the time. If the user doesn't mention an epic, **ask**: "Should this be under an epic? (paste a SAAS key, describe it, or say 'no')". This single question saves time since most tickets need an epic.

**How to detect epic references (natural language):**
- "in the X epic" / "under the X epic" / "part of X" / "belongs to X epic"
- "epic: SAAS-1234" / "parent: SAAS-1234" / "under SAAS-1234"
- Any mention of a SAAS ticket key that turns out to be an Epic
- "no epic" / "none" / "skip" → do not set a parent

**How to resolve the epic:**
1. If the user gives a **ticket key** (e.g., "SAAS-18371"), use it directly as the `parent` value.
2. If the user gives a **name or description** (e.g., "in the ERM epic", "under the RabbitMQ replacement epic"), search for it:
   - Use JQL: `project = SAAS AND issuetype = Epic AND statusCategory != Done AND summary ~ "<search terms>" ORDER BY created DESC`
   - If exactly one match, use it. If multiple, show the top 3 and ask the user to pick.
   - If none found, tell the user and ask for the ticket key.

Set via `parent` parameter: `parent: "SAAS-18371"`

## Sprint Assignment

Determine the sprint based on the nature of the work. 91% of dev-created tickets are assigned to a sprint.

1. **Search for active sprints** using JQL: `project = SAAS AND sprint in openSprints()` with the `searchJiraIssuesUsingJql` tool. Fetch at least 2 results to find both sprints. The sprint data is in the `customfield_10010` field. If the first result only shows one sprint, run a second query excluding that sprint ID to find the other.

2. **Identify sprints by name:** Sprint names follow the pattern `CommCare [Product|Platform] [Name]`. Look for "Product" or "Platform" in the sprint name to classify them. Do NOT rely on specific sprint names — they change every sprint cycle.

3. **Classify the work using natural language:**
   - **Platform/Infra** — infrastructure, DevOps, Ansible, performance, scaling, security, database, migrations, Celery, Kafka, ElasticSearch, CouchDB, Postgres, deploys, monitoring, dependencies, CI/CD, server, AWS, Docker, Redis, RabbitMQ, nginx, SSL, backups, networking, DNS, pillow errors, connection spikes, OOM, memory spikes, downsizing machines, IAM, S3 → assign to the sprint with **"Platform"** in its name
   - **Product** — features, UI, UX, bug fixes in user-facing areas, app builder, reports, exports, case management, forms, mobile, web apps, user management, messaging, SMS, formplayer, formbuilder, data cleaning, data exports, case importer, enterprise console, feature flags, save to case, form submissions, FF deletion, add-ons, mobile app, Android → assign to the sprint with **"Product"** in its name

4. If the user says "backlog" anywhere in their description, do NOT assign a sprint (leave it in the backlog).

5. If you can't determine which sprint, **ask the user**: "Product sprint or Platform sprint? (or backlog)"

Set sprint via `additional_fields`: `"customfield_10010": <sprint_id_number>` (plain integer, NOT an object).

## Components

**Do not set components.** Developers on this team never use them (0% of dev-created tickets have components). Only set a component if the user **explicitly asks** for one (e.g., "component: Formplayer").

If explicitly requested, use `additional_fields`: `"components": [{"name": "Component Name"}]`

## Description

Whether to include a description depends on how much detail the user provided:

- **If the user provides detail beyond a simple title**, write a brief description in markdown. Use bullet points for lists. Include any links the user mentions.
- **If the input is just a title or short phrase**, skip the description. 36% of dev-created tickets have no description — a self-explanatory summary is often sufficient.
- **For Bugs**, if the user provides enough context, structure as:
  - **Observation:** What's wrong
  - **Steps to Reproduce:** If provided
  - Links, error messages, or context
- Keep descriptions concise. Don't pad with boilerplate.

## Steps

1. Parse `$ARGUMENTS` to extract: summary, description details, issue type, effort, priority, assignee, epic, and sprint intent.
2. **Resolve assignee and look up sprints** — these can run in parallel:
   - If a name is mentioned, look them up with `lookupJiraAccountId`.
   - Otherwise, get current user via `atlassianUserInfo` (for self-assignment).
   - Search for active sprints.
3. Craft a clean **summary**...
