Lookup Table APIs
==================

Lookup tables (also known as fixtures) hold reference data — such as
price lists or facility catalogues — shared across a project space's
mobile workers. Three specifications cover them:

- `Lookup Tables v1 <https://www.commcarehq.org/api/docs/lookup-table-v1/>`_
  lists, creates, updates and deletes lookup tables themselves — the
  ``tag`` and field definitions, not the row data.

- `Lookup Table Items v1
  <https://www.commcarehq.org/api/docs/lookup-table-item-v1/>`_ lists,
  creates, updates and deletes the rows (items) of a lookup table.

- `Lookup Table Items v2
  <https://www.commcarehq.org/api/docs/lookup-table-item-v2/>`_ manages
  the same rows as v1, and additionally returns the created or updated
  row in the response body for write requests.
