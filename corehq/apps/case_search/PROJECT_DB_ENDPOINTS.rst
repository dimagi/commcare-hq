Running Project DB Endpoints in Case Search
===========================================

Case search endpoints can be configured with SQL, but that SQL is only
validated — nothing runs it. This adds the two paths that do: the query tester
on the endpoint edit page, and case search itself.

See ``CASE_SEARCH_ENDPOINTS.rst`` for the Elasticsearch side of the same
feature.

Background
----------

An endpoint's ``target_type`` selects how it is configured. Elasticsearch
endpoints hold a query spec built in the query builder. Project DB endpoints
hold SQL in ``CaseSearchEndpointVersion.dangerous_sql``, checked on save by
``translate()`` and otherwise unused.

Two pieces already exist and are consumed rather than rebuilt:

- ``project_db.user_sql.translate`` converts a strict subset of SQL into a
  SQLAlchemy selectable, binding every literal so no value reaches the
  statement text.
- ``project_db.user_sql.UserSQL`` wraps that with parameter handling. ``:name``
  in the SQL becomes a required bind; ``UserSQL.parameters`` lists what the
  caller must supply; ``UserSQL.run(values, max_rows)`` executes.

The response constraint
-----------------------

Case search returns case XML, not rows::

    cases = get_case_search_results(...)
    fixtures = CaseDBFixture(cases).fixture

``UserSQL.run()`` returns ``QueryResult(columns, rows, duration)``. Something
has to turn rows into cases.

Project DB rows already carry everything a case needs. A case type's table has
the case metadata as static columns (``case_id``, ``case_name``, ``owner_id``,
and so on) and each case property as ``prop__<name>``, with the raw untruncated
property name in the column's Postgres comment. The table's own comment is the
raw case type.

So cases are built from the rows directly. No second fetch, no reconciliation
between two sources, and the ordering an ``ORDER BY`` produces is the ordering
the caller sees.

This also removes a question that the alternative raised.
``CommCareCase.objects.get_cases(case_ids)`` takes no domain — it fetches by id
across shards — so hydrating that way would have needed an explicit domain
filter to guarantee an endpoint could not return another domain's case.
Building the cases ourselves, ``domain`` is an input, not something read back
from a row.

The projection contract
-----------------------

The runtime needs to know which column holds the case id, so a project DB
endpoint's SQL must project exactly one column named ``case_id``.

"Exactly one" is load-bearing. SQLAlchemy's ``.c`` collection collapses
duplicate names, so on a join the naive check passes while the value read is
whichever table came last::

    SELECT * FROM parent JOIN child ON parent.case_id = child.parent_id
        .c keys   =['case_id', 'name', 'parent_id']
        inner_cols=['case_id', 'name', 'case_id', 'parent_id', 'name']
        emitted   =parent.case_id, parent.name, child.case_id,
                   child.parent_id, child.name

SQLAlchemy warns about the collapse, and a row with two ``case_id`` labels is
ambiguous at the DBAPI level regardless. So the check reads ``inner_columns``,
not ``.c``, and rejects duplicates. Aliasing resolves it and leaves the author
in control of which table is the case::

    SELECT parent.case_id AS pid, child.case_id FROM parent JOIN child ...

``inner_columns`` does not exist on a ``CompoundSelect``, so a ``UNION``
collects the columns of every leg via ``.selects``.

The matching columns must also all belong to one table, which is what makes
the results a single case type with a single set of property columns. A
``UNION`` of two case types is therefore rejected; a ``UNION`` of two queries
against the same table is fine.

Everything else about the projection is the author's choice. Selecting fewer
columns produces a smaller case; ``SELECT case_id FROM patient`` yields a case
with an id and nothing else. That is deliberate: it lets an author keep the
payload small when a case list only needs a few properties.

Components
----------

``project_db.cases.rows_to_cases(rows, domain, table)``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Builds ``CommCareCase`` objects from project DB rows, setting only what the row
actually contains.

.. code-block:: python

    _CASE_COLUMNS = {
        'case_id': 'case_id', 'case_name': 'name', 'owner_id': 'owner_id',
        'opened_on': 'opened_on', 'closed_on': 'closed_on', 'closed': 'closed',
        'modified_on': 'modified_on',
        'server_modified_on': 'server_modified_on',
        'external_id': 'external_id',
    }


    def rows_to_cases(rows, domain, table):
        """Build cases from project DB rows, using only the columns selected."""
        prop_columns = [c for c in table.columns if c.name.startswith('prop__')]
        cases = []
        for row in rows:
            present = set(row.keys())
            cases.append(CommCareCase(
                domain=domain,
                type=table.comment,
                indices=[],
                case_json={c.comment: row[c.name] for c in prop_columns
                           if c.name in present and row[c.name]},
                **{attr: row[col] for col, attr in _CASE_COLUMNS.items()
                   if col in present},
            ))
        return cases

Notes on the details, each of which is a thing that would otherwise go wrong:

- Lookups are guarded against ``row.keys()``. A missing column raises
  ``NoSuchColumnError`` rather than returning ``None``, so an unguarded
  ``row['case_name']`` would break ``SELECT case_id FROM patient``.
- ``startswith('prop__')`` excludes the typed duplicate columns
  (``date_prop__dob``), which hold coerced values. Case properties are strings.
- ``c.comment`` recovers the raw property name. Postgres identifiers are capped
  at 63 bytes, so long names are truncated with a hash suffix; the comment is
  the only place the original survives.
- ``indices=[]`` is explicit. An unsaved case already returns ``[]`` without a
  query, because ``case_id`` is not the primary key and so ``is_saved()`` is
  false — but ``CaseDBXMLGenerator.add_indices`` reads ``case.indices`` for
  every case, and relying on that short circuit silently makes the behaviour
  depend on model internals.

Save-time validation
~~~~~~~~~~~~~~~~~~~~

``CaseSearchEndpointForm._clean_sql`` keeps its current ``translate()`` call
and adds the projection check described above, reported as a field error.

Runtime
~~~~~~~

``get_endpoint_results`` forks on ``target_type``. The existing body becomes
the Elasticsearch branch — it must not run for a project DB endpoint, whose
stored ``query`` and ``case_type`` are ``None``, so ``parse_query_spec`` would
fail.

The project DB branch:

1. ``UserSQL(domain, version.dangerous_sql)``
2. Bind ``config.criteria`` by name to ``UserSQL.parameters``, as strings.
   Postgres coerces to int and date at the comparison.
3. ``run()``, then locate the ``case_id`` column and its table.
4. ``rows_to_cases(...)``.

Criteria that do not match the SQL's parameters are an error, not silently
dropped — ``UserSQL._clean_parameters`` already raises ``BadParameters`` on a
mismatch.

The row limit is the same one Elasticsearch endpoints use:

.. code-block:: python

    def resolve_max_results(domain):
        if toggles.INCREASED_MAX_SEARCH_RESULTS.enabled(domain):
            return 1500
        return CASE_SEARCH_MAX_RESULTS

That block currently appears twice in ``utils.py``, in both
``_get_initial_search_es`` methods, so this extracts it rather than adding a
third copy. The toggle is labelled for Elasticsearch, but what it expresses is
a per-domain cap on search results, which applies equally here.

Two behavioural differences from the Elasticsearch branch, both accepted for
now and listed under `Follow up`_:

- Elasticsearch endpoints apply ``.is_closed(False)`` and so never return
  closed cases. A project DB endpoint returns whatever the SQL selects; the
  table has a ``closed`` column, so excluding them is the author's job.
- A data registry is ignored. Project DB stores one schema per domain, so a
  project DB endpoint only ever searches its own domain.

Query tester
~~~~~~~~~~~~

``CaseSearchEndpointTestView`` forks the same way, rendering
``UserSQL.get_info()`` and ``run()`` into ``test_results.html``. Unlike the
runtime it shows every selected column, since seeing the query's actual output
is the point.

Parameters card
~~~~~~~~~~~~~~~

Hidden for project DB endpoints. ``UserSQL.parameters``, derived from the
``:name`` placeholders in the SQL, is the contract; a second declared list
would be a second source of truth to keep in sync.

Testing
-------

- ``rows_to_cases`` against a real reflected table: full projection, a minimal
  ``SELECT case_id`` projection, a truncated property name, and a property
  whose value is empty.
- Projection validation: accepted and rejected shapes, including the join
  ambiguity and both union legs.
- Runtime: an endpoint returning cases, a parameterised endpoint, and a
  criteria/parameter mismatch.
- Tester: results rendered, and a translator error rendered as an error.

Follow up
---------

Deferred deliberately. Each is a behaviour a reader of the code would
otherwise be right to flag as a bug.

**Closed cases are returned.** Elasticsearch endpoints apply
``.is_closed(False)``; project DB endpoints return whatever the SQL selects.
The author can add ``WHERE closed = false``, but nothing prompts them to, and
an endpoint ported from Elasticsearch will quietly return more cases than it
used to. The alternative is appending the filter in the runtime, which means
rewriting the author's query — against the grain of everything else here — so
the better fix is probably surfacing it in the editor.

**Data registries are ignored.** A request carrying
``x_commcare_data_registry`` gets a ``RegistryQueryHelper`` whose
``get_base_queryset`` spans ``visible_domains``, and Elasticsearch endpoints
honour it. Project DB has one schema per domain, so the query runs against the
endpoint's own domain and nothing else: no error, fewer cases than asked for,
and no ``COMMCARE_PROJECT`` tags on the results. Both can be set on the same
request today, so this is reachable rather than theoretical.

**One case type per endpoint.** The ``case_id`` columns must all come from
one table, so an endpoint cannot return a mix of case types — a ``UNION``
across two of them is rejected. Elasticsearch endpoints have the same limit,
querying ``[endpoint.current_version.case_type]``, so this is parity rather
than a new restriction. Lifting it means ``rows_to_cases`` resolving the
table per row instead of once, and the rows do not currently say which table
they came from.

**Case indices.** Results carry no ``<index>`` elements. Project DB stores
``parent_id`` and ``host_id`` but not identifier, referenced type, or
relationship, so the rows cannot reconstruct them; Elasticsearch-backed
endpoints get them from the index. Closing this costs one bulk query —
``CommCareCaseIndex.objects.get_related_indices(domain, case_ids)`` with
``attach_prefetch_models(..., 'cached_indices')``, the mechanism
``get_cases(prefetched_indices=...)`` uses — and should be done once a real
endpoint needs relationships.

**Deleted cases.** Project DB has no ``deleted`` column, so a row may outlive
the case's deletion. Whether the populate pipeline removes such rows needs
confirming before this runs anywhere real.

**Date ranges.** Values bind as strings, so
``__range__YYYY-MM-DD__YYYY-MM-DD`` criteria are not usable yet. The path is
already open: ``ARRAY_OPS`` maps ``exp.ArrayContainedBy`` to ``<@``, which is
also Postgres' range containment operator, so ``WHERE dob <@ :dob`` needs no
translator change — only a bound value that is a ``daterange`` rather than a
string. ``SearchCriteria.get_date_range()`` already parses the criteria
format. Parameter binding is therefore kept as a dict of name to value, with
nothing assuming the value is a string.

Branching
---------

``riese/cs_endpoint_sql_base`` merges ``es/projdb-advanced-queries`` (#38065)
and ``riese/cs_endpoint_sql`` (#38069). Work branches off it and rebases onto
master as each lands.
