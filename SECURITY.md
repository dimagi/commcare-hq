# Security Policy

## About

Dimagi, the maker of CommCare, takes the security of our software products and services seriously. 

For more information about CommCare’s security policies, please visit the Dimagi Trust Center.

## Reporting a vulnerability

Please report suspected security vulnerabilities **privately**. Do not open a
public GitHub issue or pull request, and do not post details to the CommCare
forum, for a security issue.

Email your report to **`support@dimagi.com`**.

When you report, please include as much of the following as you can:

- A description of the vulnerability and its impact.
- Steps to reproduce, or a proof of concept.
- The affected component(s), endpoint(s), or file(s), and the commit or
  deployment you tested against.
- Any suggested remediation, if you have one.

## What to expect

- We aim to acknowledge your report within **5 business days**.
- We follow **coordinated disclosure**: we ask that you give us a reasonable
  opportunity to release a fix before any public disclosure. With your
  permission, we are glad to credit you in the resulting advisory.

For confirmed vulnerabilities we publish a fix and, where appropriate, a
[GitHub Security Advisory](https://github.com/dimagi/commcare-hq/security/advisories).

## Supported versions

CommCare HQ is continuously delivered: it is deployed from the `master` branch,
and there are no long-term maintenance branches. Security fixes are applied to
`master`. Self-hosted operators should track `master` and deploy updates
regularly so that security fixes are picked up promptly through their normal
deploy process.
