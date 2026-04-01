# Context

The User Audit Report is a very useful frontend to the auditcare database tables
that are used to store access logs enriched with app-specific context
(primarily the user account and domain associated with the request).

However, the report has some limitations that significantly impact its ability to
meet the needs of our support and security teams, and hamper our ability to get
quick and accurate answers in the heat of the moment.

# Goal
We want to add a few improvements to this report to be able to more flexibly
and reliably query the data that already exists in the underlying database.

Specifically:

- Results Limit and Truncation:
  - The current limit of 4,000 queries should be increased to 5,000.
  - When the limit is reached, rather than refuse to perform the query, it should
    execute the query with limit 5,001, identify the last timestamp for which the query would have returned 5,000 or below, update the page's filter to reflect that timestamp, highlight this in the UI, and display a message to the user explaining this.
    (We need to be particularly careful with the edge cases here, such as whether we're querying with < or <= semantics, whether there are multiple trailing records with exactly the same timestamp, etc. so that the result set that is returned
    matches exactly what would have been returned had the user originally made the query
    that we updated the page to reflect.)
- Enhanced Filtering Capabilities:
  - Add the ability to search by IP address or IP Range. Search text may be
    - An exact IP address
    - CIDR syntax, but only ending in `/8`, `/16`, `/24`, or `/32`
      - `/32` results in the same query as exact match
      - The others result in a "starts with" condition matching the prefix
        up through one, two, or three `.` characters, respectively.
      - Multiple of the above, comma separated, interpreted as matching *any*
        of the conditions (i.e. combined using `OR`).
  - Add the ability to search by URL
    - Should include both a "contains" and "starts with" option
      When using a URL "starts with" filter while also using the domain filter
      it should helpfully note if the URL prefix you're searching for does not start with
      `/a/<domain>/`, with `<domain>` matching the domain you're searching for.
    - Allow *excluding* URL patterns as well.
      - Can exclude multiple URLs, newline separated.
- Chronological sortable date format:
  - The way date/times are currently written prevents chronological sorting, leading to events being shown out of order.
  - Fixed by switching to a timestamp format
    such as “2026-03-27T15:17:52.132987Z” or “2026-03-27 15:17:52.132987 UTC”.
    (Match precident for similar UTC format already used elsewhere in the codebase.)
- Additional Columns:
  - Include the status code of the response as one of the columns in the report
