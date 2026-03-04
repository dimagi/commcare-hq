---
name: jira-cve
description: Create a security ticket in JIRA for a CVE from a GitHub Dependabot alert URL.
argument-hint: <github_dependabot_alert_url>
---

# Create CVE Jira Ticket

Given a GitHub Dependabot security alert URL, fetch the alert details and
create a security ticket in the SAAS project using the standard CommCare HQ
format.

## Input

`$ARGUMENTS` — A GitHub Dependabot security alert URL. Examples:

- `/jira-cve https://github.com/dimagi/commcare-hq/security/dependabot/740`
- `/jira-cve https://github.com/dimagi/commcare-android/security/dependabot/12`

## Step 1: Fetch Alert Data

Parse the URL to extract `<owner>/<repo>` and `<alert_number>`, then run:

```bash
gh api repos/<owner>/<repo>/dependabot/alerts/<alert_number>
```

From the response, extract:

| Field | JSON path |
|---|---|
| Package name | `dependency.package.name` |
| Ecosystem | `dependency.package.ecosystem` |
| Severity | `security_advisory.severity` |
| CVE ID | `security_advisory.cve_id` (may be null) |
| Patched version | `security_vulnerability.first_patched_version.identifier` |
| Summary/description | `security_advisory.summary` |
| Alert URL | `html_url` (use this as the GitHub link; falls back to the original `$ARGUMENTS` URL if absent) |

**Ecosystem mapping:**

| GitHub ecosystem | Ticket label |
|---|---|
| `pip` | `py` |
| `npm` | `js` |
| `maven` | `java` |
| anything else | use the raw value |

**Repo label:** use only the repository name portion of the URL (e.g.
`commcare-hq`, `commcare-android`), not the full `owner/repo`.

## Defaults & Constants

- **Project:** `SAAS` (always)
- **Cloud ID:** `dbff467f-3c3f-4ced-a2ba-a29e1941edd6`
- **Component:** `Data Privacy / Security` (always)
- **Effort Range field:** `customfield_10160`
- **Sprint field:** `customfield_10010`

## Title Format

The summary **must** follow this exact format:

```
[Security: <repo> <py|js> <level>] Upgrade <package> to <patched_version> or later
```

Examples:
- `[Security: commcare-hq py high] Upgrade pillow to 10.3.0 or later`
- `[Security: commcare-hq js critical] Upgrade lodash to 4.17.21 or later`

## Severity / Priority Mapping

| Severity | Jira Priority | Jira ID |
|---|---|---|
| critical | P1 | `1` |
| high | P2 | `2` |
| medium | P3 | `3` |
| low | P5 | `5` |

Always set `priority` via `additional_fields`: `"priority": {"id": "<id>"}`.

## Assignee

Assign to self — use `atlassianUserInfo` to get the current authenticated
user's account ID.

## Description

Structure the description as:

```
**Package:** <package>
**Patched version:** <patched_version> or later
**Ecosystem:** <py|js>
<If CVE ID present: **CVE:** <CVE-ID> — https://www.cve.org/CVERecord?id=<CVE-ID>>
**GitHub alert:** <original URL from $ARGUMENTS>

<security_advisory.summary from the alert>

**Fix:** Upgrade `<package>` to `<patched_version>` or later in the relevant
dependency file (requirements/*.txt or package.json as appropriate).
```

## Issue Type

Always `Task`.

## Effort Range

Default to `Hours` (`10384`) — dependency upgrades are typically small.

## Sprint

Security work is Platform work. Search for the active Platform sprint:

1. Use JQL: `project = SAAS AND sprint in openSprints()` to find active sprints.
2. Assign to the sprint whose name contains **"Platform"**.

Set sprint via `additional_fields`: `"customfield_10010": <sprint_id_number>`.

## Epic

Assume no epic.

## Steps

1. Parse the URL from `$ARGUMENTS` to extract `owner/repo` and alert number.
2. Run `gh api repos/<owner>/<repo>/dependabot/alerts/<alert_number>` to fetch
   alert data.
3. Extract package, ecosystem, severity, patched version, CVE ID, and summary.
4. Ask the user: "Should this go under a security epic? Paste a SAAS key or say 'no'."
5. Construct the formatted summary and description (see formats above).
6. Delegate to the `/jira-ticket` skill by invoking it with a single string
   argument that contains all the relevant information:

   ```
   /jira-ticket <formatted_summary>. Component: Data Privacy / Security. <priority>. Platform sprint. Description — Package: <package>, Patched version: <patched_version> or later, Ecosystem: <py|js>, CVE: <CVE-ID> (<cve_url>), GitHub alert: <alert_html_url>. <advisory_summary>. Fix: upgrade <package> to <patched_version> or later in the relevant dependency file.<if epic:  Epic: <SAAS-key>.>
   ```

   **Always include the GitHub alert URL** (`html_url` from the API response, or the original `$ARGUMENTS` URL as fallback) in the description. This is required so the ticket links back to the Dependabot alert.

   The `/jira-ticket` skill will handle assignee lookup, sprint resolution, and
   ticket creation.

   **Important:** Pass the priority explicitly using the label (e.g. "P2") so
   `jira-ticket` picks it up. Pass the component as "Component: Data Privacy /
   Security" so it is set correctly.
