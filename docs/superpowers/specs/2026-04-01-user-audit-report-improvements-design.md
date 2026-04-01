# User Audit Report Improvements — Design Spec

## Overview

Enhance the existing `UserAuditReport` in `corehq/apps/hqadmin/reports.py` to support
more flexible querying, better result handling, and additional data columns. All changes
modify the existing report in place.

## 1. Result Limit & Smart Truncation

### Current behavior
- `MAX_RECORDS = 4000`
- If query would return >4,000 rows, refuse to execute and show a warning. No results displayed.

### New behavior
- `MAX_RECORDS = 5000`
- Always execute the query (up to `MAX_RECORDS + 1` rows), sorted by `event_date` ascending.
- **≤5,000 rows returned**: Display all results. No truncation message.
- **5,001 rows returned** (limit hit): Perform in-memory truncation:
  1. Walk backward from row 5,001 to find the latest timestamp `T` such that the count
     of rows with `event_date < T_floored` is ≤5,000, where `T_floored` is `T` truncated
     to the minute (zeroing out seconds and microseconds). This ensures the cutoff aligns
     with the minute-level granularity of the time filter.
  2. Trim the result set to only rows with `event_date < T_floored`.
  3. Update the displayed **end date** and **end time** filter values to reflect `T_floored`.
  4. Show an info-level message above the results table:
     "Showing events through {T_floored formatted}. Your query returned more than 5,000
     results; the end date/time has been adjusted. Change the end time to see later events."
- **Same-minute edge case**: If all 5,001 rows fall within the same minute (i.e. truncation
  to a minute boundary would eliminate all rows), show the first 5,000 rows and display a
  warning: "Showing 5,000 results, but there are additional events within the same minute
  that are not shown. Try narrowing by username, domain, IP address, or other filters to
  see all results."

### Key invariant
The returned rows (in the normal truncation case) exactly match what the user would have
gotten if they had originally set the end date/time filter to the adjusted value. No
off-by-one, no `<` vs `<=` discrepancy.

### Implementation notes
- Remove `_is_limit_exceeded()` method entirely.
- The `rows` property fetches up to 5,001 rows, then applies truncation logic in memory.
- No second database query is needed.

## 2. New Filters

All filters follow the standard composition rule: **OR within a filter, AND across filters.**

### 2a. IP Address Filter

- **Widget**: Text input (`IPAddressFilter`).
- **Accepted formats**:
  - Single IP: `192.168.1.1` → exact match (`ip_address = '192.168.1.1'`)
  - CIDR notation (restricted):
    - `/32` → exact match
    - `/24` → prefix match on first 3 octets (`ip_address LIKE '192.168.1.%'` / `startswith='192.168.1.'`)
    - `/16` → prefix match on first 2 octets (`startswith='192.168.'`)
    - `/8` → prefix match on first octet (`startswith='192.'`)
  - Comma-separated: multiple of the above, OR'd together.
- **Validation**: Only `/8`, `/16`, `/24`, `/32` CIDR suffixes accepted. Invalid input shows a warning.
- **ORM**: Builds `Q(ip_address=...) | Q(ip_address__startswith=...)` chains.

### 2b. URL Include Filter

- **Widget**: Textarea (newline-separated patterns, OR'd) with a dropdown toggle for
  "contains" or "starts with" mode.
- **Behavior**:
  - "contains" → `Q(path__contains=pattern)` (OR'd across patterns)
  - "starts with" → `Q(path__startswith=pattern)` (OR'd across patterns)
  - Matches against the `path` field (URL path only, no query string). Query string
    filtering is out of scope.
  - When "starts with" is selected and a domain filter is also active, show an informational
    note if the URL prefix does not start with `/a/<domain>/`:
    "Note: URLs for this domain typically start with `/a/<domain>/`."
- **Empty**: No URL include filter means "all URLs" (so exclude-only queries work).

### 2c. URL Exclude Filter

- **Widget**: Textarea (newline-separated patterns) with a dropdown toggle for
  "contains" or "starts with" mode (independent of the include toggle).
- **Behavior**: Applied as AND-NOT. A row is included only if it matches none of the
  exclude patterns.
  - "contains" → exclude rows where `path__contains=pattern` for any pattern
  - "starts with" → exclude rows where `path__startswith=pattern` for any pattern

### 2d. Status Code Filter

- **Widget**: Text input, comma-separated integers (e.g. `200, 403, 500`).
- **Default**: Empty = show all status codes (no filtering).
- **ORM**: `Q(status_code__in=[...])` for NavigationEventAudit. AccessAudit events have
  no status code — they are included when no status code filter is active, excluded when
  a status code filter is active.

## 3. Date Format

- Change from passing `event_date` as a datetime object to formatting it as a string:
  `"%Y-%m-%d %H:%M:%S.%f UTC"` (e.g. `2026-03-27 15:17:52.132987 UTC`).
- This matches codebase precedent (cf. `SERVER_DATETIME_FORMAT` + UTC suffix pattern in
  `corehq/apps/hqadmin/views/users.py`).
- Enables correct lexicographic sorting on the client side (DataTables).
- Applied in `get_generic_log_event_row()` in `corehq/apps/auditcare/utils/export.py`.

## 4. Column Changes

### New column order
1. Date
2. Doc Type
3. Username
4. Domain
5. IP Address
6. Action
7. URL *(renamed from "Resource")*
8. Status Code *(new)*
9. Description

### Details
- **"Resource" → "URL"**: Rename only; the underlying data (`request_path` / `path`) is
  always a URL path.
- **"Status Code"**: `event.status_code` for `NavigationEventAudit`; empty string for
  `AccessAudit` (which has no status code field).

## 5. Filter Layout

- Flat list matching the existing report framework convention (no grouping).
- Filter order: DatespanFilter, SimpleStartTime, SimpleEndTime, SimpleUsername,
  SimpleOptionalDomain, UserAuditActionFilter, IPAddressFilter, URLIncludeFilter,
  URLExcludeFilter, StatusCodeFilter.
- Grouped filter sections (Time / Identity / Request) deferred to a follow-up.

## 6. Template Changes

- The template currently shows either a warning OR results (never both).
- Update to support showing an info/warning message **above** the results table when
  truncation occurs, with results still displayed below.
- Remove the current "more than 4,000 records" blocking warning logic.

## Files to Modify

- `corehq/apps/hqadmin/reports.py` — report class, columns, truncation logic, filter list
- `corehq/apps/auditcare/utils/export.py` — row formatting, date format, column rename,
  query helpers for new filters
- `corehq/apps/reports/filters/simple.py` — new filter widgets (IP, URL include/exclude,
  status code)
- `corehq/apps/hqadmin/templates/hqadmin/user_audit_report.html` — template for
  truncation message display
- `corehq/apps/reports/filters/select.py` — if URL mode toggle needs a select-based filter
