# Auditcare & the User Audit Report

Auditcare (`corehq.apps.auditcare`) records HTTP requests and login/logout
events to the `NavigationEventAudit` and `AccessAudit` database tables. Each
record captures the timestamp, username, domain, IP address, URL path, HTTP
method, response status code, and selected request headers.

The **User Audit Report** (`/hq/admin/user_audit_report/`) provides a filterable
view over these records for support and security investigations.

## Filters

All filters combine with **AND**. Filters that accept multiple values combine
those values with **OR**.

**Date Range & Time** — Select a start and end date. Optionally narrow within a
day using the start/end time fields (`HH:MM` format). An end time of `00:00`
means "include the full day".

**Username** — One or more usernames, comma-separated. Leave blank to include
all users (requires a domain filter).

**Domain** — Filter to events for a single domain. Optional if username is set.

**Action** — HTTP method (`GET`, `POST`, `PUT`, `DELETE`) or access type
(`Login`, `Logout`, `Login failed`).

**IP Address** — Accepts:
- A single IP: `192.168.1.1`
- CIDR notation (`/8`, `/16`, `/24`, `/32` only): `10.0.0.0/8` matches any IP
  starting with `10.`.
- Comma-separated for multiple: `10.0.0.0/8, 192.168.1.0/24`

**URL Path Include** — One URL path pattern per line. Choose **contains** or
**starts with** mode. Rows matching any pattern are included. Leave blank to
include all paths.

When using "starts with" with a domain filter, the report shows a hint if your
patterns don't start with `/a/<domain>/`, since most domain-scoped URL paths
follow that convention.

**URL Path Exclude** — Same format as URL Path Include. Rows matching any
pattern are excluded. Has its own independent contains/starts-with toggle.

**Status Code** — Comma-separated HTTP status codes, e.g. `200, 403, 500`. When
active, only `NavigationEventAudit` rows with a matching status code are shown
(`AccessAudit` events, which have no status code, are excluded).

## Columns

| Column | Description |
|---|---|
| Date | UTC timestamp (`YYYY-MM-DD HH:MM:SS.ffffff UTC`). Sorts chronologically with client-side column sorting. |
| Doc Type | `NavigationEventAudit` or `AccessAudit`. |
| Username | The user who made the request or logged in/out. |
| Domain | The domain associated with the request, if any. |
| IP Address | Client IP address. |
| Action | HTTP method (`GET`, `POST`, etc.) for navigation events; `Login` / `Logout` / `Login failed` for access events. |
| URL | The request path (navigation events) or login path (access events). Includes query string for navigation events. |
| Status Code | HTTP response status code (navigation events only). |
| Description | Additional context (typically the username). |

## Result limit & truncation

The report returns at most **5,000 rows**. When a query matches more than 5,000
events:

1. The report fetches 5,001 rows sorted by date.
2. It finds the minute boundary of the 5,001st row and trims the result set to
   all rows strictly before that minute.
3. The end date and end time filters update on the page to reflect the new
   boundary.
4. An info message explains the adjustment and suggests setting the start time
   to the displayed cutoff to page forward.

If all 5,001 rows fall within the same minute (making minute-boundary trimming
impossible), the report shows the first 5,000 rows with a warning that
additional events in that minute are not displayed.

## Underlying models

**`NavigationEventAudit`** — Records HTTP requests. Key fields: `user`,
`domain`, `event_date`, `path`, `params` (query string), `ip_address`,
`status_code`, `headers` (JSON including `REQUEST_METHOD`).

**`AccessAudit`** — Records login, logout, and failed login events. Key fields:
`user`, `domain`, `event_date`, `path`, `ip_address`, `access_type` (`i` =
login, `o` = logout, `f` = failed).

Both models inherit from `AuditEvent` and are partitioned monthly by
`event_date`.
