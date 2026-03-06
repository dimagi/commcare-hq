---
name: cve
description: Create a Jira security ticket for a CVE and upgrade the dependency via a PR.
argument-hint: <github_dependabot_alert_url>
---

# Fix CVE End-to-End

Given a GitHub Dependabot security alert URL, create the Jira ticket and upgrade the dependency.

## Input

`$ARGUMENTS` — A GitHub Dependabot security alert URL. Example:

- `/cve https://github.com/dimagi/commcare-hq/security/dependabot/740`

## Step 1: Create the Jira Ticket

Invoke `/jira-cve` with the URL from `$ARGUMENTS`. Let it run to completion and note the Jira ticket key (e.g. `SAAS-1234`) and its URL (`https://dimagi.atlassian.net/browse/SAAS-1234`).

## Step 2: Upgrade the Dependency

From the Dependabot alert (already fetched by `/jira-cve`), identify the package name.

Invoke `/dependency-upgrade <package>`. When it creates the PR, ensure the Jira ticket URL is included in the Technical Summary alongside the changelog link.
