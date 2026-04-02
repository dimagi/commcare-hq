# User Audit Report Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the User Audit Report with smart truncation (5,000 limit), IP/URL/status code filters, chronologically-sortable date format, and a new Status Code column.

**Architecture:** Modify the existing `UserAuditReport` class and its supporting utilities in place. New filter widgets extend `BaseSimpleFilter`. All new query filtering goes through Django ORM `Q` objects built in the export utilities. The truncation logic operates in-memory on an already-fetched result set.

**Tech Stack:** Python, Django ORM, Django templates (Bootstrap 3)

---

### File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `corehq/apps/auditcare/utils/export.py` | Modify | Date formatting, column data (rename Resource→URL, add status code), new filter query builders for IP/URL/status code |
| `corehq/apps/hqadmin/reports.py` | Modify | Report class: new filters list, truncation logic, column headers, report context |
| `corehq/apps/reports/filters/simple.py` | Modify | New filter widgets: `IPAddressFilter`, `URLIncludeFilter`, `URLExcludeFilter`, `StatusCodeFilter` |
| `corehq/apps/reports/templates/reports/filters/bootstrap3/textarea_with_select.html` | Create | Template for URL filters (textarea + mode dropdown) |
| `corehq/apps/hqadmin/templates/hqadmin/user_audit_report.html` | Modify | Support showing info/warning messages above results (not instead of) |
| `corehq/apps/auditcare/tests/test_export.py` | Modify | Tests for date formatting, new row format, IP/URL/status code query builders |
| `corehq/apps/hqadmin/tests/test_user_audit_report.py` | Create | Tests for truncation logic, filter parsing, IP address validation |

---

### Task 1: Date Format Change

Update `get_generic_log_event_row()` to format `event_date` as a chronologically-sortable UTC string instead of passing a raw datetime object.

**Files:**
- Modify: `corehq/apps/auditcare/utils/export.py:151-162`
- Modify: `corehq/apps/auditcare/tests/test_export.py:95-135`

- [ ] **Step 1: Write the failing test**

In `corehq/apps/auditcare/tests/test_export.py`, add a test for the new date format. Add this after the `TestNavigationEventsQueries` class:

```python
from ..utils.export import get_generic_log_event_row


class TestGetGenericLogEventRow(AuditcareTest):

    def test_date_format_is_sortable_utc_string(self):
        event = NavigationEventAudit(
            user="test@test.com",
            event_date=datetime(2026, 3, 27, 15, 17, 52, 132987),
            ip_address="10.0.0.1",
            path="/a/test/dashboard/",
            headers={"REQUEST_METHOD": "GET"},
            status_code=200,
        )
        row = get_generic_log_event_row(event)
        self.assertEqual(row[0], "2026-03-27 15:17:52.132987 UTC")

    def test_date_format_with_zero_microseconds(self):
        event = NavigationEventAudit(
            user="test@test.com",
            event_date=datetime(2026, 3, 27, 15, 17, 52, 0),
            ip_address="10.0.0.1",
            path="/a/test/dashboard/",
            headers={"REQUEST_METHOD": "GET"},
            status_code=200,
        )
        row = get_generic_log_event_row(event)
        self.assertEqual(row[0], "2026-03-27 15:17:52.000000 UTC")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest corehq/apps/auditcare/tests/test_export.py::TestGetGenericLogEventRow -v --reusedb=1`
Expected: FAIL — `row[0]` is a datetime object, not a string.

- [ ] **Step 3: Implement the date format change**

In `corehq/apps/auditcare/utils/export.py`, modify `get_generic_log_event_row()`:

```python
def get_generic_log_event_row(event):
    action, resource = get_action_and_resource(event)
    return [
        event.event_date.strftime("%Y-%m-%d %H:%M:%S.%f UTC"),
        event.doc_type,
        event.user,
        event.domain or '',
        event.ip_address,
        action,
        resource,
        event.description,
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest corehq/apps/auditcare/tests/test_export.py::TestGetGenericLogEventRow -v --reusedb=1`
Expected: PASS

- [ ] **Step 5: Fix the existing CSV export test**

The `test_write_export_from_all_log_events` test in the same file expects `'Date': '2021-02-01 03:00:00'` but the format now includes microseconds and UTC suffix. Update the expected values in that test:

Change every occurrence of `'Date': '2021-02-01 03:00:00'` to `'Date': '2021-02-01 03:00:00.000000 UTC'`.

- [ ] **Step 6: Run the full export test suite**

Run: `pytest corehq/apps/auditcare/tests/test_export.py -v --reusedb=1`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add corehq/apps/auditcare/utils/export.py corehq/apps/auditcare/tests/test_export.py
git commit -m "Change audit event date format to sortable UTC string"
```

---

### Task 2: Column Changes (Rename Resource→URL, Add Status Code)

Rename the "Resource" column to "URL" and add a "Status Code" column in the correct position.

**Files:**
- Modify: `corehq/apps/auditcare/utils/export.py:137-167`
- Modify: `corehq/apps/hqadmin/reports.py:187-198`
- Modify: `corehq/apps/auditcare/tests/test_export.py`

- [ ] **Step 1: Write failing tests for new row format**

Add these tests to the `TestGetGenericLogEventRow` class in `corehq/apps/auditcare/tests/test_export.py`:

```python
    def test_row_includes_status_code_for_navigation_event(self):
        event = NavigationEventAudit(
            user="test@test.com",
            event_date=datetime(2026, 3, 27, 15, 0),
            ip_address="10.0.0.1",
            path="/a/test/dashboard/",
            headers={"REQUEST_METHOD": "GET"},
            status_code=200,
        )
        row = get_generic_log_event_row(event)
        # Columns: Date, DocType, Username, Domain, IP, Action, URL, StatusCode, Description
        self.assertEqual(len(row), 9)
        self.assertEqual(row[6], "/a/test/dashboard/")  # URL (was Resource)
        self.assertEqual(row[7], 200)  # Status Code

    def test_row_has_empty_status_code_for_access_event(self):
        event = AccessAudit(
            user="test@test.com",
            event_date=datetime(2026, 3, 27, 15, 0),
            ip_address="10.0.0.1",
            path="/a/test/login/",
            access_type="i",
        )
        row = get_generic_log_event_row(event)
        self.assertEqual(len(row), 9)
        self.assertEqual(row[7], "")  # Status Code empty for AccessAudit
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest corehq/apps/auditcare/tests/test_export.py::TestGetGenericLogEventRow::test_row_includes_status_code_for_navigation_event -v --reusedb=1`
Expected: FAIL — row has 8 elements, not 9.

- [ ] **Step 3: Update `get_generic_log_event_row` to include status code**

In `corehq/apps/auditcare/utils/export.py`, modify `get_generic_log_event_row()`:

```python
def get_generic_log_event_row(event):
    action, resource = get_action_and_resource(event)
    status_code = event.status_code if event.doc_type == 'NavigationEventAudit' else ''
    return [
        event.event_date.strftime("%Y-%m-%d %H:%M:%S.%f UTC"),
        event.doc_type,
        event.user,
        event.domain or '',
        event.ip_address,
        action,
        resource,
        status_code,
        event.description,
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest corehq/apps/auditcare/tests/test_export.py::TestGetGenericLogEventRow -v --reusedb=1`
Expected: PASS

- [ ] **Step 5: Update the CSV export header and test**

In `corehq/apps/auditcare/utils/export.py`, update the `write_export_from_all_log_events` header row (line 167):

```python
writer.writerow(['Date', 'Type', 'User', 'Domain', 'IP Address', 'Action', 'URL', 'Status Code', 'Description'])
```

Update the `test_write_export_from_all_log_events` test to expect "URL" instead of "Resource" as a column name, and to account for the new "Status Code" column if unpacking those fields. (The test only unpacks Date, Type, User, Description — so the header change alone should be sufficient here.)

- [ ] **Step 6: Update report column headers**

In `corehq/apps/hqadmin/reports.py`, modify the `headers` property:

```python
    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(gettext_lazy("Date")),
            DataTablesColumn(gettext_lazy("Doc Type")),
            DataTablesColumn(gettext_lazy("Username")),
            DataTablesColumn(gettext_lazy("Domain")),
            DataTablesColumn(gettext_lazy("IP Address")),
            DataTablesColumn(gettext_lazy("Action")),
            DataTablesColumn(gettext_lazy("URL")),
            DataTablesColumn(gettext_lazy("Status Code")),
            DataTablesColumn(gettext_lazy("Description")),
        )
```

- [ ] **Step 7: Run full test suite for auditcare**

Run: `pytest corehq/apps/auditcare/tests/test_export.py -v --reusedb=1`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add corehq/apps/auditcare/utils/export.py corehq/apps/hqadmin/reports.py corehq/apps/auditcare/tests/test_export.py
git commit -m "Rename Resource column to URL and add Status Code column"
```

---

### Task 3: New Filter Widgets

Create the four new filter widgets: IP Address, URL Include, URL Exclude, and Status Code.

**Files:**
- Modify: `corehq/apps/reports/filters/simple.py`
- Create: `corehq/apps/reports/templates/reports/filters/bootstrap3/textarea_with_select.html`
- Create: `corehq/apps/hqadmin/tests/test_user_audit_report.py`

- [ ] **Step 1: Write tests for IP address parsing and validation**

Create `corehq/apps/hqadmin/tests/test_user_audit_report.py`:

```python
from django.test import RequestFactory, TestCase

from corehq.apps.reports.filters.simple import IPAddressFilter


class TestIPAddressParsing(TestCase):

    def test_single_ip(self):
        result = IPAddressFilter.parse_ip_input("192.168.1.1")
        self.assertEqual(result, [("exact", "192.168.1.1")])

    def test_cidr_32(self):
        result = IPAddressFilter.parse_ip_input("192.168.1.1/32")
        self.assertEqual(result, [("exact", "192.168.1.1")])

    def test_cidr_24(self):
        result = IPAddressFilter.parse_ip_input("192.168.1.0/24")
        self.assertEqual(result, [("startswith", "192.168.1.")])

    def test_cidr_16(self):
        result = IPAddressFilter.parse_ip_input("172.16.0.0/16")
        self.assertEqual(result, [("startswith", "172.16.")])

    def test_cidr_8(self):
        result = IPAddressFilter.parse_ip_input("10.0.0.0/8")
        self.assertEqual(result, [("startswith", "10.")])

    def test_comma_separated(self):
        result = IPAddressFilter.parse_ip_input("10.0.0.0/8, 192.168.1.0/24")
        self.assertEqual(result, [
            ("startswith", "10."),
            ("startswith", "192.168.1."),
        ])

    def test_invalid_cidr_suffix(self):
        result = IPAddressFilter.parse_ip_input("10.0.0.0/12")
        self.assertEqual(result, None)

    def test_empty_input(self):
        result = IPAddressFilter.parse_ip_input("")
        self.assertEqual(result, [])

    def test_whitespace_only(self):
        result = IPAddressFilter.parse_ip_input("   ")
        self.assertEqual(result, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest corehq/apps/hqadmin/tests/test_user_audit_report.py::TestIPAddressParsing -v --reusedb=1`
Expected: FAIL — `IPAddressFilter` does not exist.

- [ ] **Step 3: Implement IPAddressFilter**

In `corehq/apps/reports/filters/simple.py`, add:

```python
class IPAddressFilter(BaseSimpleFilter):
    slug = 'ip_address'
    label = gettext_lazy("IP Address")
    help_inline = gettext_lazy(
        "Single IP, CIDR (/8, /16, /24, /32), or comma-separated. "
        "Example: 10.0.0.0/8, 192.168.1.1"
    )

    ALLOWED_CIDR = {8: 1, 16: 2, 24: 3, 32: None}  # suffix -> number of octets for prefix

    @staticmethod
    def parse_ip_input(raw_input):
        """Parse IP address filter input.

        Returns:
            list of (match_type, value) tuples on success, where match_type is
            "exact" or "startswith".
            None if any entry has an invalid CIDR suffix.
            Empty list if input is blank.
        """
        if not raw_input or not raw_input.strip():
            return []

        results = []
        for entry in raw_input.split(","):
            entry = entry.strip()
            if not entry:
                continue
            if "/" in entry:
                ip, suffix = entry.rsplit("/", 1)
                try:
                    suffix_int = int(suffix)
                except ValueError:
                    return None
                if suffix_int not in IPAddressFilter.ALLOWED_CIDR:
                    return None
                octets_needed = IPAddressFilter.ALLOWED_CIDR[suffix_int]
                if octets_needed is None:
                    results.append(("exact", ip))
                else:
                    octets = ip.split(".")
                    prefix = ".".join(octets[:octets_needed]) + "."
                    results.append(("startswith", prefix))
            else:
                results.append(("exact", entry))
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest corehq/apps/hqadmin/tests/test_user_audit_report.py::TestIPAddressParsing -v --reusedb=1`
Expected: PASS

- [ ] **Step 5: Create textarea_with_select template**

Create `corehq/apps/reports/templates/reports/filters/bootstrap3/textarea_with_select.html`:

```html
{% extends 'reports/filters/bootstrap3/base.html' %}
{% block filter_content %}
  <select id="{{ css_id }}_mode" name="{{ slug }}_mode" class="form-control" style="margin-bottom: 5px;">
    {% for val, text in mode_options %}
      <option value="{{ val }}" {% if val == selected_mode %}selected{% endif %}>{{ text }}</option>
    {% endfor %}
  </select>
  <textarea
    id="{{ css_id }}"
    name="{{ slug }}"
    class="form-control"
    rows="3"
    placeholder="{{ placeholder }}"
  >{{ default }}</textarea>
  {% if help_inline %}
    <p class="help-block">
      <i class="fa fa-info-circle"></i>
      {{ help_inline }}
    </p>
  {% endif %}
{% endblock %}
```

- [ ] **Step 6: Implement URL Include, URL Exclude, and Status Code filters**

In `corehq/apps/reports/filters/simple.py`, add:

```python
class URLIncludeFilter(BaseSimpleFilter):
    slug = 'url_include'
    label = gettext_lazy("URL Include")
    template = "reports/filters/bootstrap3/textarea_with_select.html"
    help_inline = gettext_lazy(
        "One URL pattern per line. Patterns are OR'd together. "
        "Leave blank to include all URLs."
    )

    @property
    def filter_context(self):
        from corehq.apps.reports.util import DatatablesServerSideParams
        return {
            'default': DatatablesServerSideParams.get_value_from_request(
                self.request, self.slug, default_value=""
            ),
            'help_inline': self.help_inline,
            'mode_options': [("contains", "contains"), ("startswith", "starts with")],
            'selected_mode': self.request.GET.get(f'{self.slug}_mode', 'contains'),
            'placeholder': '/a/domain/api/v1/',
        }


class URLExcludeFilter(BaseSimpleFilter):
    slug = 'url_exclude'
    label = gettext_lazy("URL Exclude")
    template = "reports/filters/bootstrap3/textarea_with_select.html"
    help_inline = gettext_lazy(
        "One URL pattern per line. Matching rows are excluded. "
        "Patterns are OR'd (any match excludes the row)."
    )

    @property
    def filter_context(self):
        from corehq.apps.reports.util import DatatablesServerSideParams
        return {
            'default': DatatablesServerSideParams.get_value_from_request(
                self.request, self.slug, default_value=""
            ),
            'help_inline': self.help_inline,
            'mode_options': [("contains", "contains"), ("startswith", "starts with")],
            'selected_mode': self.request.GET.get(f'{self.slug}_mode', 'contains'),
            'placeholder': '/a/domain/heartbeat/',
        }


class StatusCodeFilter(BaseSimpleFilter):
    slug = 'status_code'
    label = gettext_lazy("Status Code")
    help_inline = gettext_lazy(
        "Comma-separated status codes. Example: 200, 403, 500. "
        "Leave blank to include all."
    )

    @staticmethod
    def parse_status_codes(raw_input):
        """Parse comma-separated status codes.

        Returns a list of integers, or empty list if blank.
        Returns None if any entry is not a valid integer.
        """
        if not raw_input or not raw_input.strip():
            return []
        codes = []
        for entry in raw_input.split(","):
            entry = entry.strip()
            if not entry:
                continue
            try:
                codes.append(int(entry))
            except ValueError:
                return None
        return codes
```

- [ ] **Step 7: Run linting on the filters file**

Run: `ruff check corehq/apps/reports/filters/simple.py`
Expected: No errors (or fix any that appear)

- [ ] **Step 8: Commit**

```bash
git add corehq/apps/reports/filters/simple.py \
       corehq/apps/reports/templates/reports/filters/bootstrap3/textarea_with_select.html \
       corehq/apps/hqadmin/tests/test_user_audit_report.py
git commit -m "Add IP address, URL include/exclude, and status code filter widgets"
```

---

### Task 4: Query Builders for New Filters

Add functions to build ORM `Q` objects for IP address, URL, and status code filtering.

**Files:**
- Modify: `corehq/apps/auditcare/utils/export.py`
- Modify: `corehq/apps/auditcare/tests/test_export.py`

- [ ] **Step 1: Write failing tests for IP address query building**

In `corehq/apps/auditcare/tests/test_export.py`, add:

```python
from django.db.models import Q

from ..utils.export import build_ip_filter, build_url_include_filter, build_url_exclude_filter


class TestBuildIPFilter(AuditcareTest):

    def test_exact_match(self):
        q = build_ip_filter([("exact", "10.0.0.1")])
        self.assertEqual(q, Q(ip_address="10.0.0.1"))

    def test_prefix_match(self):
        q = build_ip_filter([("startswith", "10.")])
        self.assertEqual(q, Q(ip_address__startswith="10."))

    def test_multiple_or(self):
        q = build_ip_filter([("exact", "10.0.0.1"), ("startswith", "192.168.")])
        self.assertEqual(q, Q(ip_address="10.0.0.1") | Q(ip_address__startswith="192.168."))

    def test_empty_returns_none(self):
        q = build_ip_filter([])
        self.assertIsNone(q)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest corehq/apps/auditcare/tests/test_export.py::TestBuildIPFilter -v --reusedb=1`
Expected: FAIL — `build_ip_filter` does not exist.

- [ ] **Step 3: Implement `build_ip_filter`**

In `corehq/apps/auditcare/utils/export.py`, add after the imports:

```python
from django.db.models import Q
```

Then add the function:

```python
def build_ip_filter(parsed_ips):
    """Build a Q object for IP address filtering.

    Args:
        parsed_ips: list of (match_type, value) tuples from IPAddressFilter.parse_ip_input()

    Returns:
        Q object, or None if the list is empty.
    """
    if not parsed_ips:
        return None
    q = Q()
    for match_type, value in parsed_ips:
        if match_type == "exact":
            q |= Q(ip_address=value)
        elif match_type == "startswith":
            q |= Q(ip_address__startswith=value)
    return q
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest corehq/apps/auditcare/tests/test_export.py::TestBuildIPFilter -v --reusedb=1`
Expected: PASS

- [ ] **Step 5: Write failing tests for URL filter query building**

In `corehq/apps/auditcare/tests/test_export.py`, add:

```python
class TestBuildURLFilters(AuditcareTest):

    def test_include_contains(self):
        q = build_url_include_filter(["/api/v1/"], "contains")
        self.assertEqual(q, Q(path__contains="/api/v1/"))

    def test_include_startswith(self):
        q = build_url_include_filter(["/a/test/"], "startswith")
        self.assertEqual(q, Q(path__startswith="/a/test/"))

    def test_include_multiple_or(self):
        q = build_url_include_filter(["/api/", "/dashboard/"], "contains")
        self.assertEqual(q, Q(path__contains="/api/") | Q(path__contains="/dashboard/"))

    def test_include_empty_returns_none(self):
        q = build_url_include_filter([], "contains")
        self.assertIsNone(q)

    def test_exclude_contains(self):
        q = build_url_exclude_filter(["/heartbeat/"], "contains")
        self.assertEqual(q, ~Q(path__contains="/heartbeat/"))

    def test_exclude_startswith(self):
        q = build_url_exclude_filter(["/a/test/heartbeat/"], "startswith")
        self.assertEqual(q, ~Q(path__startswith="/a/test/heartbeat/"))

    def test_exclude_multiple_and_not(self):
        q = build_url_exclude_filter(["/heartbeat/", "/ping/"], "contains")
        self.assertEqual(q, ~Q(path__contains="/heartbeat/") & ~Q(path__contains="/ping/"))

    def test_exclude_empty_returns_none(self):
        q = build_url_exclude_filter([], "contains")
        self.assertIsNone(q)
```

- [ ] **Step 6: Implement `build_url_include_filter` and `build_url_exclude_filter`**

In `corehq/apps/auditcare/utils/export.py`, add:

```python
def build_url_include_filter(patterns, mode):
    """Build a Q object for URL include filtering.

    Args:
        patterns: list of URL pattern strings
        mode: "contains" or "startswith"

    Returns:
        Q object, or None if the list is empty.
    """
    if not patterns:
        return None
    lookup = f"path__{mode}"
    q = Q()
    for pattern in patterns:
        q |= Q(**{lookup: pattern})
    return q


def build_url_exclude_filter(patterns, mode):
    """Build a Q object for URL exclude filtering.

    Args:
        patterns: list of URL pattern strings
        mode: "contains" or "startswith"

    Returns:
        Q object (negated), or None if the list is empty.
    """
    if not patterns:
        return None
    lookup = f"path__{mode}"
    q = Q()
    for pattern in patterns:
        q &= ~Q(**{lookup: pattern})
    return q
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest corehq/apps/auditcare/tests/test_export.py::TestBuildURLFilters -v --reusedb=1`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add corehq/apps/auditcare/utils/export.py corehq/apps/auditcare/tests/test_export.py
git commit -m "Add query builders for IP address and URL filtering"
```

---

### Task 5: Integrate New Filters into the Report

Wire up the new filter widgets and query builders into `UserAuditReport`, updating the query pipeline to apply IP, URL, and status code filtering.

**Files:**
- Modify: `corehq/apps/hqadmin/reports.py:114-277`
- Modify: `corehq/apps/auditcare/utils/export.py:27-50`

- [ ] **Step 1: Add filter imports and fields list**

In `corehq/apps/hqadmin/reports.py`, add the new filters to the `fields` list:

```python
    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.simple.SimpleStartTime',
        'corehq.apps.reports.filters.simple.SimpleEndTime',
        'corehq.apps.reports.filters.simple.SimpleUsername',
        'corehq.apps.reports.filters.simple.SimpleOptionalDomain',
        'corehq.apps.reports.filters.select.UserAuditActionFilter',
        'corehq.apps.reports.filters.simple.IPAddressFilter',
        'corehq.apps.reports.filters.simple.URLIncludeFilter',
        'corehq.apps.reports.filters.simple.URLExcludeFilter',
        'corehq.apps.reports.filters.simple.StatusCodeFilter',
    ]
```

- [ ] **Step 2: Add properties to read new filter values from the request**

In `corehq/apps/hqadmin/reports.py`, add these properties to `UserAuditReport` after `selected_action`:

```python
    @property
    def selected_ip_addresses(self):
        """Parse IP address filter input. Returns list of (match_type, value) tuples, or None on error."""
        from corehq.apps.reports.filters.simple import IPAddressFilter
        raw = self.request.GET.get('ip_address', '')
        return IPAddressFilter.parse_ip_input(raw)

    @property
    def selected_url_include_patterns(self):
        """Parse URL include filter input. Returns list of non-empty pattern strings."""
        raw = self.request.GET.get('url_include', '')
        return [line.strip() for line in raw.splitlines() if line.strip()]

    @property
    def selected_url_include_mode(self):
        return self.request.GET.get('url_include_mode', 'contains')

    @property
    def selected_url_exclude_patterns(self):
        """Parse URL exclude filter input. Returns list of non-empty pattern strings."""
        raw = self.request.GET.get('url_exclude', '')
        return [line.strip() for line in raw.splitlines() if line.strip()]

    @property
    def selected_url_exclude_mode(self):
        return self.request.GET.get('url_exclude_mode', 'contains')

    @property
    def selected_status_codes(self):
        """Parse status code filter input. Returns list of ints, or None on error."""
        from corehq.apps.reports.filters.simple import StatusCodeFilter
        raw = self.request.GET.get('status_code', '')
        return StatusCodeFilter.parse_status_codes(raw)
```

- [ ] **Step 3: Update the query functions to accept new filter parameters**

In `corehq/apps/auditcare/utils/export.py`, update `navigation_events_by_user` and `access_events_by_user` to accept and apply new Q filters:

```python
def navigation_events_by_user(user, domain=None, start_date=None, end_date=None, action=None,
                               extra_filters=None):
    where = filters_for_audit_event_query(user, domain, start_date, end_date)
    query = NavigationEventAudit.objects.filter(**where)
    if action:
        query = query.extra(
            where=["headers::jsonb->>'REQUEST_METHOD' = %s"],
            params=[action]
        )
    if extra_filters:
        query = query.filter(extra_filters)
    return AuditWindowQuery(query)


def access_events_by_user(user, domain=None, start_date=None, end_date=None, action=None,
                           extra_filters=None):
    where = filters_for_audit_event_query(user, domain, start_date, end_date)
    if action:
        where['access_type'] = action
    query = AccessAudit.objects.filter(**where)
    if extra_filters:
        query = query.filter(extra_filters)
    return AuditWindowQuery(query)


def all_audit_events_by_user(user, domain=None, start_date=None, end_date=None, action=None,
                              nav_extra_filters=None, access_extra_filters=None):
    return chain(
        navigation_events_by_user(user, domain, start_date, end_date, action,
                                   extra_filters=nav_extra_filters),
        access_events_by_user(user, domain, start_date, end_date, action,
                               extra_filters=access_extra_filters),
    )
```

- [ ] **Step 4: Build and pass Q filters from the report's `rows` property**

In `corehq/apps/hqadmin/reports.py`, add an import at the top:

```python
from corehq.apps.auditcare.utils.export import (
    all_audit_events_by_user,
    build_ip_filter,
    build_url_exclude_filter,
    build_url_include_filter,
    get_generic_log_event_row,
)
```

Then add a helper method to `UserAuditReport`:

```python
    def _build_extra_filters(self, for_navigation=True):
        """Build Q object combining all extra filters for a model type.

        Args:
            for_navigation: True for NavigationEventAudit, False for AccessAudit
        """
        filters = Q()

        ip_parsed = self.selected_ip_addresses
        if ip_parsed:  # not empty list and not None
            ip_q = build_ip_filter(ip_parsed)
            if ip_q:
                filters &= ip_q

        url_include = build_url_include_filter(
            self.selected_url_include_patterns, self.selected_url_include_mode
        )
        if url_include:
            filters &= url_include

        url_exclude = build_url_exclude_filter(
            self.selected_url_exclude_patterns, self.selected_url_exclude_mode
        )
        if url_exclude:
            filters &= url_exclude

        status_codes = self.selected_status_codes
        if status_codes:  # not empty list and not None
            if for_navigation:
                filters &= Q(status_code__in=status_codes)
            else:
                # AccessAudit has no status code; exclude when filtering by status code
                return None  # signals to skip AccessAudit entirely

        return filters if filters != Q() else None
```

Update the `rows` property to use it (this replaces the current query call):

```python
    @property
    def rows(self):
        if not (self.selected_domain or self.selected_user):
            return []

        nav_filters = self._build_extra_filters(for_navigation=True)
        access_filters = self._build_extra_filters(for_navigation=False)

        rows = []
        events = all_audit_events_by_user(
            self.selected_user, self.selected_domain, self.start_datetime, self.end_datetime,
            self.selected_action,
            nav_extra_filters=nav_filters,
            access_extra_filters=access_filters,
        )
        for event in events:
            row = get_generic_log_event_row(event)
            rows.append(row)

        return sorted(rows, key=lambda x: x[0])
```

Note: `access_extra_filters=None` (returned when status codes are filtered) will cause `access_events_by_user` to still run. We need to handle the "skip AccessAudit" case. Update `all_audit_events_by_user`:

```python
def all_audit_events_by_user(user, domain=None, start_date=None, end_date=None, action=None,
                              nav_extra_filters=None, access_extra_filters=None,
                              skip_access=False):
    nav = navigation_events_by_user(user, domain, start_date, end_date, action,
                                     extra_filters=nav_extra_filters)
    if skip_access:
        return nav
    access = access_events_by_user(user, domain, start_date, end_date, action,
                                    extra_filters=access_extra_filters)
    return chain(nav, access)
```

And update `_build_extra_filters` and `rows` to use a flag approach:

```python
    @property
    def rows(self):
        if not (self.selected_domain or self.selected_user):
            return []

        nav_filters = self._build_nav_filters()
        access_filters = self._build_access_filters()
        skip_access = access_filters is False  # False means "skip entirely"

        rows = []
        events = all_audit_events_by_user(
            self.selected_user, self.selected_domain, self.start_datetime, self.end_datetime,
            self.selected_action,
            nav_extra_filters=nav_filters,
            access_extra_filters=None if skip_access else access_filters,
            skip_access=skip_access,
        )
        for event in events:
            row = get_generic_log_event_row(event)
            rows.append(row)

        return sorted(rows, key=lambda x: x[0])

    def _build_common_filters(self):
        """Build Q objects for filters shared by both model types."""
        filters = Q()

        ip_parsed = self.selected_ip_addresses
        if ip_parsed:
            ip_q = build_ip_filter(ip_parsed)
            if ip_q:
                filters &= ip_q

        url_include = build_url_include_filter(
            self.selected_url_include_patterns, self.selected_url_include_mode
        )
        if url_include:
            filters &= url_include

        url_exclude = build_url_exclude_filter(
            self.selected_url_exclude_patterns, self.selected_url_exclude_mode
        )
        if url_exclude:
            filters &= url_exclude

        return filters if filters != Q() else None

    def _build_nav_filters(self):
        """Build combined Q for NavigationEventAudit."""
        filters = self._build_common_filters() or Q()
        status_codes = self.selected_status_codes
        if status_codes:
            filters &= Q(status_code__in=status_codes)
        return filters if filters != Q() else None

    def _build_access_filters(self):
        """Build combined Q for AccessAudit. Returns False to skip AccessAudit entirely."""
        status_codes = self.selected_status_codes
        if status_codes:
            return False  # AccessAudit has no status code
        return self._build_common_filters()
```

- [ ] **Step 5: Add validation warning for invalid IP input**

In the `report_context` property, add a check for invalid IP input after the existing validations:

```python
    @property
    def report_context(self):
        context = super().report_context

        if not (self.selected_domain or self.selected_user):
            context['warning_message'] = _("You must specify either a username or a domain. "
                    "Requesting all audit events across all users and domains would exceed system limits.")
        elif self._is_invalid_time_range():
            context['warning_message'] = _("The end time cannot be earlier than the start time when "
                    "both dates are the same. Please adjust your time range.")
        elif self.selected_ip_addresses is None:
            context['warning_message'] = _(
                "Invalid IP address filter. Use single IPs, CIDR notation "
                "(/8, /16, /24, /32), or comma-separated combinations."
            )
        elif self.selected_status_codes is None:
            context['warning_message'] = _(
                "Invalid status code filter. Use comma-separated integers (e.g. 200, 403, 500)."
            )

        # URL domain hint
        if (self.selected_url_include_mode == 'startswith'
                and self.selected_domain
                and self.selected_url_include_patterns):
            domain_prefix = f'/a/{self.selected_domain}/'
            if not any(p.startswith(domain_prefix) for p in self.selected_url_include_patterns):
                context.setdefault('info_message', '')
                context['info_message'] += _(
                    'Note: URLs for this domain typically start with "{domain_prefix}".'
                ).format(domain_prefix=domain_prefix)

        return context
```

- [ ] **Step 6: Run linting**

Run: `ruff check corehq/apps/hqadmin/reports.py corehq/apps/auditcare/utils/export.py`
Expected: No errors (or fix any)

- [ ] **Step 7: Commit**

```bash
git add corehq/apps/hqadmin/reports.py corehq/apps/auditcare/utils/export.py
git commit -m "Wire up IP, URL, and status code filters into audit report queries"
```

---

### Task 6: Smart Truncation Logic

Replace the "refuse to execute" behavior with smart in-memory truncation at minute boundaries.

**Files:**
- Modify: `corehq/apps/hqadmin/reports.py`
- Modify: `corehq/apps/hqadmin/tests/test_user_audit_report.py`

- [ ] **Step 1: Write failing tests for the truncation function**

In `corehq/apps/hqadmin/tests/test_user_audit_report.py`, add:

```python
from datetime import datetime, date, time

from corehq.apps.hqadmin.reports import truncate_rows_to_minute_boundary


class TestTruncateRowsToMinuteBoundary(TestCase):

    def _make_row(self, event_date):
        """Create a minimal row list matching the report format.
        Index 0 is the formatted date string."""
        return [event_date.strftime("%Y-%m-%d %H:%M:%S.%f UTC")] + [""] * 8

    def test_no_truncation_under_limit(self):
        rows = [self._make_row(datetime(2026, 3, 27, 15, m)) for m in range(10)]
        result, cutoff_dt = truncate_rows_to_minute_boundary(rows, max_records=5000)
        self.assertEqual(len(result), 10)
        self.assertIsNone(cutoff_dt)

    def test_truncation_at_minute_boundary(self):
        # 3 rows at 15:00, 3 rows at 15:01, 3 rows at 15:02 = 9 rows
        rows = []
        for minute in [0, 1, 2]:
            for second in [10, 20, 30]:
                rows.append(self._make_row(datetime(2026, 3, 27, 15, minute, second)))
        result, cutoff_dt = truncate_rows_to_minute_boundary(rows, max_records=8)
        # Should truncate to rows with event_date < 15:02:00, which gives us 6 rows (15:00 and 15:01)
        self.assertEqual(len(result), 6)
        self.assertEqual(cutoff_dt, datetime(2026, 3, 27, 15, 2))

    def test_truncation_same_minute_edge_case(self):
        # All rows in the same minute
        rows = [self._make_row(datetime(2026, 3, 27, 15, 0, s)) for s in range(10)]
        result, cutoff_dt = truncate_rows_to_minute_boundary(rows, max_records=8)
        # Can't trim meaningfully — return first max_records rows
        self.assertEqual(len(result), 8)
        self.assertIsNone(cutoff_dt)  # None signals same-minute edge case

    def test_truncation_preserves_sort_order(self):
        rows = []
        for minute in [0, 1, 2, 3]:
            rows.append(self._make_row(datetime(2026, 3, 27, 15, minute, 30)))
        result, cutoff_dt = truncate_rows_to_minute_boundary(rows, max_records=3)
        # Truncate to < 15:03:00, giving us rows at 15:00, 15:01, 15:02
        self.assertEqual(len(result), 3)
        self.assertEqual(cutoff_dt, datetime(2026, 3, 27, 15, 3))

    def test_truncation_large_cluster_at_boundary(self):
        # 2 rows at 15:00, 5 rows at 15:01 = 7 total, limit=6
        rows = []
        for s in [10, 20]:
            rows.append(self._make_row(datetime(2026, 3, 27, 15, 0, s)))
        for s in [10, 20, 30, 40, 50]:
            rows.append(self._make_row(datetime(2026, 3, 27, 15, 1, s)))
        result, cutoff_dt = truncate_rows_to_minute_boundary(rows, max_records=6)
        # Can only keep rows < 15:01:00, which is the 2 rows at 15:00
        self.assertEqual(len(result), 2)
        self.assertEqual(cutoff_dt, datetime(2026, 3, 27, 15, 1))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest corehq/apps/hqadmin/tests/test_user_audit_report.py::TestTruncateRowsToMinuteBoundary -v --reusedb=1`
Expected: FAIL — `truncate_rows_to_minute_boundary` does not exist.

- [ ] **Step 3: Implement `truncate_rows_to_minute_boundary`**

In `corehq/apps/hqadmin/reports.py`, add this function (outside the class, near the top):

```python
def truncate_rows_to_minute_boundary(rows, max_records):
    """Truncate a sorted row list to a clean minute boundary.

    Rows must be sorted by date ascending (index 0 is the formatted date string).

    Args:
        rows: list of row lists, sorted by date string at index 0
        max_records: the maximum number of records to return

    Returns:
        (truncated_rows, cutoff_datetime) tuple.
        - If no truncation needed: (rows, None)
        - If truncated to a minute boundary: (trimmed_rows, cutoff_datetime)
          where cutoff_datetime is the minute floored datetime used as the boundary
          (rows with event_date < cutoff_datetime are kept)
        - If all rows fall in the same minute (can't trim meaningfully):
          (rows[:max_records], None) — caller should show a same-minute warning
    """
    if len(rows) <= max_records:
        return rows, None

    def parse_date(date_str):
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f UTC")

    def floor_to_minute(dt):
        return dt.replace(second=0, microsecond=0)

    # Find the minute of the row that pushed us over the limit
    overflow_date = parse_date(rows[max_records][0])
    overflow_minute = floor_to_minute(overflow_date)

    # Find the minute of the first row
    first_minute = floor_to_minute(parse_date(rows[0][0]))

    # If all rows are in the same minute, we can't trim
    if overflow_minute == first_minute:
        return rows[:max_records], None

    # Trim to rows with event_date < overflow_minute
    cutoff = overflow_minute
    trimmed = [r for r in rows if parse_date(r[0]) < cutoff]

    # Edge case: if this still exceeds max_records (shouldn't happen with
    # minute flooring since we're cutting at the overflow row's minute),
    # but guard against it
    if len(trimmed) > max_records:
        # Recurse with the trimmed set
        return truncate_rows_to_minute_boundary(trimmed, max_records)

    return trimmed, cutoff
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest corehq/apps/hqadmin/tests/test_user_audit_report.py::TestTruncateRowsToMinuteBoundary -v --reusedb=1`
Expected: PASS

- [ ] **Step 5: Integrate truncation into the `rows` property and `report_context`**

Replace the `rows` property in `UserAuditReport` with:

```python
    MAX_RECORDS = 5000

    @property
    def rows(self):
        if not (self.selected_domain or self.selected_user):
            return []
        if self.selected_ip_addresses is None or self.selected_status_codes is None:
            return []

        nav_filters = self._build_nav_filters()
        access_filters = self._build_access_filters()
        skip_access = access_filters is False

        rows = []
        events = all_audit_events_by_user(
            self.selected_user, self.selected_domain, self.start_datetime, self.end_datetime,
            self.selected_action,
            nav_extra_filters=nav_filters,
            access_extra_filters=None if skip_access else access_filters,
            skip_access=skip_access,
        )
        count = 0
        for event in events:
            row = get_generic_log_event_row(event)
            rows.append(row)
            count += 1
            if count > self.MAX_RECORDS:
                break

        sorted_rows = sorted(rows, key=lambda x: x[0])

        truncated_rows, cutoff_dt = truncate_rows_to_minute_boundary(sorted_rows, self.MAX_RECORDS)
        self._truncation_cutoff = cutoff_dt
        self._truncation_same_minute = (len(sorted_rows) > self.MAX_RECORDS and cutoff_dt is None)
        return truncated_rows
```

Update `report_context` to remove the old `_is_limit_exceeded` logic and add truncation messages:

```python
    @property
    def report_context(self):
        context = super().report_context

        if not (self.selected_domain or self.selected_user):
            context['warning_message'] = _("You must specify either a username or a domain. "
                    "Requesting all audit events across all users and domains would exceed system limits.")
        elif self._is_invalid_time_range():
            context['warning_message'] = _("The end time cannot be earlier than the start time when "
                    "both dates are the same. Please adjust your time range.")
        elif self.selected_ip_addresses is None:
            context['warning_message'] = _(
                "Invalid IP address filter. Use single IPs, CIDR notation "
                "(/8, /16, /24, /32), or comma-separated combinations."
            )
        elif self.selected_status_codes is None:
            context['warning_message'] = _(
                "Invalid status code filter. Use comma-separated integers (e.g. 200, 403, 500)."
            )

        # Truncation messages (set by rows property)
        # Access rows to trigger the query and truncation logic
        _ = self.rows
        if getattr(self, '_truncation_same_minute', False):
            context['truncation_message'] = _(
                "Showing {max_records} results, but there are additional events within the "
                "same minute that are not shown. Try narrowing by username, domain, IP address, "
                "or other filters to see all results."
            ).format(max_records=self.MAX_RECORDS)
            context['truncation_level'] = 'warning'
        elif getattr(self, '_truncation_cutoff', None):
            cutoff = self._truncation_cutoff
            context['truncation_message'] = _(
                "Showing events through {cutoff_time}. Your query returned more than "
                "{max_records} results; the end date/time has been adjusted. "
                "Change the end time to see later events."
            ).format(
                cutoff_time=cutoff.strftime("%Y-%m-%d %H:%M UTC"),
                max_records=self.MAX_RECORDS,
            )
            context['truncation_level'] = 'info'
            context['adjusted_end_date'] = cutoff.strftime("%Y-%m-%d")
            context['adjusted_end_time'] = cutoff.strftime("%H:%M")

        # URL domain hint
        if (self.selected_url_include_mode == 'startswith'
                and self.selected_domain
                and self.selected_url_include_patterns):
            domain_prefix = f'/a/{self.selected_domain}/'
            if not any(p.startswith(domain_prefix) for p in self.selected_url_include_patterns):
                context.setdefault('info_message', '')
                context['info_message'] += _(
                    'Note: URLs for this domain typically start with "{domain_prefix}".'
                ).format(domain_prefix=domain_prefix)

        return context
```

- [ ] **Step 6: Remove `_is_limit_exceeded` and `_get_limit_exceeded_message`**

Delete the `_is_limit_exceeded` method (lines 221-241) and `_get_limit_exceeded_message` method (lines 273-276) from `UserAuditReport`. Remove the `@memoized` import if it's no longer used. Remove the `filters_for_audit_event_query` import if it's no longer used in this file. Remove the `AccessAudit`, `NavigationEventAudit` imports from `reports.py` if they were only used for `_is_limit_exceeded`.

- [ ] **Step 7: Run linting**

Run: `ruff check corehq/apps/hqadmin/reports.py`
Expected: No errors (or fix any)

- [ ] **Step 8: Commit**

```bash
git add corehq/apps/hqadmin/reports.py corehq/apps/hqadmin/tests/test_user_audit_report.py
git commit -m "Replace limit-exceeded blocking with smart truncation at minute boundaries"
```

---

### Task 7: Template Changes for Truncation Messages

Update the template to show info/warning messages above the results table (not instead of it).

**Files:**
- Modify: `corehq/apps/hqadmin/templates/hqadmin/user_audit_report.html`

- [ ] **Step 1: Update the template**

Replace the contents of `corehq/apps/hqadmin/templates/hqadmin/user_audit_report.html` with:

```html
{% extends "reports/bootstrap3/tabular.html" %}
{% load i18n %}
{% load hq_shared_tags %}

{% block reportcontent %}
  {% if warning_message %}
    <div class="alert alert-warning">
      <h4>
        <i class="fa-solid fa-triangle-exclamation"></i> {% trans "Warning" %}
      </h4>
      <p>{{ warning_message }}</p>
    </div>
  {% endif %}
  {% if truncation_message %}
    <div class="alert alert-{{ truncation_level }}">
      <h4>
        {% if truncation_level == 'warning' %}
          <i class="fa-solid fa-triangle-exclamation"></i> {% trans "Warning" %}
        {% else %}
          <i class="fa-solid fa-circle-info"></i> {% trans "Note" %}
        {% endif %}
      </h4>
      <p>{{ truncation_message }}</p>
    </div>
  {% endif %}
  {% if info_message %}
    <div class="alert alert-info">
      <p>{{ info_message }}</p>
    </div>
  {% endif %}
  {% if not warning_message %}
    {{ block.super }}
  {% endif %}
{% endblock reportcontent %}
```

Note: `warning_message` (e.g. no user/domain, invalid input) still blocks results. `truncation_message` shows above results but results still display. `info_message` (URL domain hint) is purely informational.

- [ ] **Step 2: Add JavaScript to update filter values on truncation**

The adjusted end date/time need to be reflected in the filter inputs. Add a script block to the template:

```html
{% block reportcontent %}
  {# ... message blocks from above ... #}
  {% if not warning_message %}
    {{ block.super }}
  {% endif %}
  {% if adjusted_end_date %}
    <script>
      document.addEventListener('DOMContentLoaded', function() {
        var endDateInput = document.querySelector('[name="enddate"]');
        var endTimeInput = document.querySelector('[name="end_time"]');
        if (endDateInput) {
          endDateInput.value = '{{ adjusted_end_date }}';
        }
        if (endTimeInput) {
          endTimeInput.value = '{{ adjusted_end_time }}';
        }
      });
    </script>
  {% endif %}
{% endblock reportcontent %}
```

Note: The exact date input name (`enddate`) should be verified by checking the `DatespanFilter` template. The implementer should inspect the rendered HTML to confirm the input names and adjust if needed.

- [ ] **Step 3: Commit**

```bash
git add corehq/apps/hqadmin/templates/hqadmin/user_audit_report.html
git commit -m "Update audit report template for truncation and info messages"
```

---

### Task 8: End-to-End Smoke Test

Verify the full report works with the new features by adding an integration test that exercises the report's `rows` property with various filter combinations.

**Files:**
- Modify: `corehq/apps/hqadmin/tests/test_user_audit_report.py`

- [ ] **Step 1: Write integration test for filter combinations**

In `corehq/apps/hqadmin/tests/test_user_audit_report.py`, add:

```python
from django.test import RequestFactory

from corehq.apps.auditcare.models import AccessAudit, NavigationEventAudit
from corehq.apps.auditcare.tests.testutils import AuditcareTest
from corehq.apps.hqadmin.reports import UserAuditReport


class TestUserAuditReportFilters(AuditcareTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        headers = {"REQUEST_METHOD": "GET"}
        NavigationEventAudit.objects.bulk_create([
            NavigationEventAudit(
                user="admin@test.com",
                domain="test-domain",
                event_date=datetime(2026, 3, 27, 15, 0, i),
                ip_address="10.0.0.1",
                path="/a/test-domain/dashboard/",
                headers=headers,
                status_code=200,
            )
            for i in range(5)
        ] + [
            NavigationEventAudit(
                user="admin@test.com",
                domain="test-domain",
                event_date=datetime(2026, 3, 27, 15, 0, 10),
                ip_address="192.168.1.100",
                path="/a/test-domain/api/v1/cases/",
                headers=headers,
                status_code=404,
            ),
        ])

    def _get_report(self, params):
        request = self.factory.get('/hq/admin/audit_events/', params)
        request.couch_user = None
        request.can_access_all_locations = True
        report = UserAuditReport(request, domain=None)
        return report

    def test_ip_filter_exact(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'ip_address': '192.168.1.100',
        })
        rows = report.rows
        self.assertEqual(len(rows), 1)
        self.assertIn('192.168.1.100', rows[0][4])

    def test_ip_filter_cidr(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'ip_address': '10.0.0.0/8',
        })
        rows = report.rows
        self.assertEqual(len(rows), 5)

    def test_status_code_filter(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'status_code': '404',
        })
        rows = report.rows
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][7], 404)

    def test_url_include_contains(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'url_include': '/api/',
            'url_include_mode': 'contains',
        })
        rows = report.rows
        self.assertEqual(len(rows), 1)

    def test_url_exclude_contains(self):
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'url_exclude': '/dashboard/',
            'url_exclude_mode': 'contains',
        })
        rows = report.rows
        self.assertEqual(len(rows), 1)  # only the API row

    def test_status_code_filter_excludes_access_events(self):
        AccessAudit.objects.create(
            user="admin@test.com",
            domain="test-domain",
            event_date=datetime(2026, 3, 27, 15, 0, 0),
            ip_address="10.0.0.1",
            path="/a/test-domain/login/",
            access_type="i",
        )
        report = self._get_report({
            'username': 'admin@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
            'status_code': '200',
        })
        rows = report.rows
        # Should only include NavigationEventAudit with status 200
        for row in rows:
            self.assertEqual(row[1], 'NavigationEventAudit')
```

- [ ] **Step 2: Run the integration tests**

Run: `pytest corehq/apps/hqadmin/tests/test_user_audit_report.py::TestUserAuditReportFilters -v --reusedb=1`

Note: These tests require database access (AuditcareTest sets the right databases). If the report instantiation requires additional request attributes or setup, adjust the `_get_report` method accordingly based on errors.

Expected: PASS (possibly after adjustments to request setup)

- [ ] **Step 3: Write integration test for truncation**

```python
class TestUserAuditReportTruncation(AuditcareTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()
        headers = {"REQUEST_METHOD": "GET"}
        # Create events spanning 3 minutes, enough to trigger truncation with small limit
        events = []
        for minute in range(3):
            for second in range(10):
                events.append(NavigationEventAudit(
                    user="bulk@test.com",
                    domain="test-domain",
                    event_date=datetime(2026, 3, 27, 15, minute, second),
                    ip_address="10.0.0.1",
                    path="/a/test-domain/dashboard/",
                    headers=headers,
                    status_code=200,
                ))
        NavigationEventAudit.objects.bulk_create(events)

    def _get_report(self, params):
        request = self.factory.get('/hq/admin/audit_events/', params)
        request.couch_user = None
        request.can_access_all_locations = True
        report = UserAuditReport(request, domain=None)
        return report

    def test_truncation_adjusts_end_time(self):
        report = self._get_report({
            'username': 'bulk@test.com',
            'startdate': '2026-03-27',
            'enddate': '2026-03-27',
        })
        # Temporarily lower MAX_RECORDS to trigger truncation
        original_max = UserAuditReport.MAX_RECORDS
        UserAuditReport.MAX_RECORDS = 25
        try:
            rows = report.rows
            self.assertLessEqual(len(rows), 25)
            context = report.report_context
            self.assertIn('truncation_message', context)
            self.assertIn('adjusted_end_date', context)
        finally:
            UserAuditReport.MAX_RECORDS = original_max
```

- [ ] **Step 4: Run all tests**

Run: `pytest corehq/apps/hqadmin/tests/test_user_audit_report.py -v --reusedb=1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add corehq/apps/hqadmin/tests/test_user_audit_report.py
git commit -m "Add integration tests for audit report filters and truncation"
```

---

### Task 9: Final Cleanup and Full Test Run

Run linting and the full test suite to catch any regressions.

**Files:** All modified files

- [ ] **Step 1: Run linting on all modified files**

```bash
ruff check corehq/apps/hqadmin/reports.py corehq/apps/auditcare/utils/export.py corehq/apps/reports/filters/simple.py
```

Expected: No errors

- [ ] **Step 2: Run import sorting**

```bash
ruff check --select I --fix corehq/apps/hqadmin/reports.py corehq/apps/auditcare/utils/export.py corehq/apps/reports/filters/simple.py corehq/apps/hqadmin/tests/test_user_audit_report.py corehq/apps/auditcare/tests/test_export.py
```

- [ ] **Step 3: Run the full auditcare and hqadmin test suites**

```bash
pytest corehq/apps/auditcare/tests/ -v --reusedb=1
pytest corehq/apps/hqadmin/tests/test_user_audit_report.py -v --reusedb=1
```

Expected: All PASS

- [ ] **Step 4: Commit any formatting changes separately**

```bash
git add -u
git commit -m "Fix import sorting and formatting"
```

(Only if there were changes from step 2.)
