# Auditcare partition pruning — design

## Problem

The `pgauditcare` database is approaching its size limit. Rather than grow it,
we want to enforce our existing data-retention policy: audit records older than
six years may be deleted. The two high-volume audit tables —
`NavigationEventAudit` and `AccessAudit` — are already range-partitioned by
month (via the `architect` library, on the `event_date` column), so old data
can be reclaimed cheaply by dropping whole partition tables rather than issuing
row-level `DELETE`s.

## Goal

A periodic Celery task that runs **once a month** and drops every monthly
partition of the two auditcare tables whose data is entirely older than
`now - AUDITCARE_RETENTION_YEARS` (default 6 years). Because this permanently
destroys compliance-relevant data, the logic must be conservative, observable,
and thoroughly tested.

## Background: how the partitions work

Both models are decorated with:

```python
@architect.install('partition', type='range', subtype='date',
                   constraint='month', column='event_date')
```

architect installs a `BEFORE INSERT` trigger on the parent table that routes
each row into a monthly child table. For the `month` constraint the child
tables are named using the PostgreSQL `TO_CHAR` pattern `"y"YYYY"m"MM`, i.e.:

```
auditcare_navigationeventaudit_y2020m01
auditcare_accessaudit_y2020m01
```

Crucially, architect also attaches a `CHECK` constraint to each child table
enforcing `event_date >= <month start> AND event_date < <next month start>`.
**This means the month encoded in a partition's name is guaranteed by the
database to bound that partition's contents.** We rely on this guarantee: if a
partition's name-month is strictly older than the retention cutoff, every row
in it is provably older than the cutoff.

The parent tables use Django's default table names —
`auditcare_navigationeventaudit` and `auditcare_accessaudit` — read at runtime
from `Model._meta.db_table` rather than hardcoded.

Reference implementation to model on: `prune_synclogs` in
`corehq/ex-submodules/casexml/apps/phone/tasks.py` (same idea, weekly instead
of monthly). We deliberately diverge from it in one respect — see below.

## Design

### Why drive off table names, not the oldest data date

`prune_synclogs` calls `Min('date')` to find where to start iterating. That
aggregates across every child partition (a scan of the very table we are
worried about being too large) and confirms nothing about a table's contents
before dropping it.

Instead we enumerate the partition tables that actually exist from the Postgres
catalog and parse the month out of each name. This is:

- **Authoritative** — the name↔date-range binding is enforced by the child
  table's `CHECK` constraint, so the name alone tells us the exact range with
  certainty; no data scan required.
- **Cheaper** — no aggregate over a huge partitioned table.
- **Gap-tolerant** — months with no audit rows simply have no partition table,
  and are handled naturally.

### Components

Two layers, so the destructive decision is a pure, directly-testable function.

**1. Pure helper (no DB, no clock):**

```python
def get_partitions_to_drop(existing_table_names, base_table, cutoff_date):
    """Return the partition table names whose month is entirely older than
    ``cutoff_date``.

    :param existing_table_names: iterable of table names present in the DB
    :param base_table: parent table name, e.g. ``auditcare_accessaudit``
    :param cutoff_date: retention boundary (a ``date``)
    :returns: sorted list of table names safe to drop
    """
```

Logic:
- Match names against `^{re.escape(base_table)}_y(\d{4})m(\d{2})$`. Names that
  don't match (including the parent table itself) are ignored.
- `cutoff_month = date(cutoff_date.year, cutoff_date.month, 1)`.
- A partition for `(year, month)` is dropped iff
  `date(year, month, 1) < cutoff_month`. The partition containing the cutoff,
  and every newer partition, is always kept. This is the conservative
  "never delete data younger than 6 years" boundary.
- Return the matching names sorted (deterministic order for logging/tests).

**2. The periodic task — thin wiring:**

```python
@periodic_task(
    run_every=crontab(hour=2, minute=0, day_of_month='1'),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'),
)
def prune_auditcare_partitions():
```

For each model in `(NavigationEventAudit, AccessAudit)`:
1. `db = router.db_for_write(Model)` — resolves the correct DB (the separate
   auditcare DB in environments where one is configured).
2. `cutoff = date.today() - relativedelta(years=settings.AUDITCARE_RETENTION_YEARS)`.
3. Query the catalog on that connection for existing partition names.
4. `to_drop = get_partitions_to_drop(existing, Model._meta.db_table, cutoff)`.
5. For each name: `DROP TABLE IF EXISTS "<name>"`, logging each drop.
6. Emit `metrics_gauge('commcare.auditcare.partitions_dropped', len(to_drop),
   tags={'model': Model.__name__})`.

Each model is handled independently and wrapped so a failure on one (or on a
single `DROP`) is logged and does not abort the rest of the run.

### Catalog query

Fetch existing partition names on the model's write connection, e.g.:

```sql
SELECT tablename FROM pg_tables WHERE tablename LIKE %s
-- param: base_table + '_y%m%'
```

The `LIKE` is only a coarse prefilter; `get_partitions_to_drop`'s regex is the
authority on what counts as a partition.

### Settings

Add to the auditcare section of `settings.py` (~line 785):

```python
AUDITCARE_RETENTION_YEARS = 6
```

Overridable per environment via `localsettings`.

### Schedule

`crontab(hour=2, minute=0, day_of_month='1')` — 02:00 on the first of each
month, an off-peak window consistent with the other pruning tasks. The task
lives in a new `corehq/apps/auditcare/tasks.py`, autodiscovered by Celery
because the auditcare app is already registered in `INSTALLED_APPS`.

### Error handling & safety

- `DROP TABLE IF EXISTS` is idempotent, so a re-run after a partial failure is
  safe and a concurrent drop can't error the task.
- The helper can never return a partition that isn't strictly older than the
  cutoff month, so no live or near-live data can be dropped even if the task
  fires at an unexpected time.
- Every dropped table name is logged; a per-model count metric supports
  monitoring/alerting on the monthly job.

## Testing

Compliance-critical, so coverage is explicit and named for intent.

**Helper unit tests** (`SimpleTestCase`, parametrized — no DB):
- Oldest partitions well before cutoff → dropped.
- Partition whose month *is* the cutoff month → **kept** (named test asserting
  the boundary is conservative).
- Partition one month before cutoff → dropped; one month after → kept.
- Year-boundary handling (e.g. cutoff in January drops the prior December).
- Multi-year span drops all sufficiently-old months.
- Empty input → empty output.
- Non-matching / foreign table names (including the bare parent table and a
  differently-prefixed table) are ignored.
- Leap-year February name parses and is handled.

**Task integration test** (`TestCase`, DB):
- Create real monthly partition tables on the auditcare DB spanning old and
  recent months, seed rows into each.
- Run `prune_auditcare_partitions`.
- Assert: partition tables older than the cutoff are gone; recent partition
  tables remain; rows younger than the cutoff are untouched (explicit
  compliance assertion); the metric reflects the number dropped.
- Covers both `NavigationEventAudit` and `AccessAudit`.

## Out of scope

- Changing the partition scheme or retention for any other table.
- Backfilling/altering historical partitions.
- A management command for manual runs (can be added later if ops wants one).
