ICDS Dashboard
==============

Information for the custom ICDS reporting dashboard. It can be accessed at \<url\>/a/\<domain\>/icds_dashboard.
Currently it's only possible for one domain on each environment to access this dashboard,
so only test locally and don't add random domains to the feature flag.

Dev Environment Setup
---------------------
The following two steps must be taken to get the dashboard to load in a development environment.
This does not include populating any data.

- Create a domain named "icds-cas"
- [Enable the feature flag](http://localhost:8000/hq/flags/edit/dashboard_icds_reports/) for that domain
- Add an `'icds-ucr'` entry to `settings.REPORTING_DATABASES` pointing at the desired key from
  `settings.DATABASES` where you want the report data tables to live.
- Update your `settings.SERVER_ENVIRONMENT` to `'icds'`

## Citus setup

To get setup on CitusDB follow [these instructions](https://github.com/dimagi/commcare-hq/blob/master/CITUSDB_SETUP.md).

## Local data

To get local dashboard data you can run:

```bash
./manage.py populate_local_db_with_icds_dashboard_test_data
```

This will populate your local database with the locations and data used in the tests
including the aggregate data.

Note that the above command is destructive to local data and read the warnings
before proceeding!

If you are using CitusDB and have already initialized the database via migrations, you will need to comment out
the `_distribute_tables_for_citus(engine)` line in `icds_reports/tests/__init__.py` for the command to succeed.

## Local UCRs

To populate local UCRs (on Citus), you can run:

```bash
./manage.py bootstrap_icds_citus icds-ucr
```

If this doesn't create them, you might want to double check your `setings.SERVER_ENVIRONMENT = 'icds'`
(assuming you are testing in a local domain named `'icds-cas'`).

Aggregate Data Tables
---------------------

child_health_monthly - unique rows for child_health case and month

agg_child_health - child_health data that is unique for location, age, gender, caste, etc

ccs_record_monthly - unique rows for ccs_record case and month

agg_ccs_record - ccs_record data that is unique for location, age, gender, caste, etc

agg_awc - unique rows for each location

Current workflow to get the data in these tables is shown [here](docs/current_state_aggregation.png)


Collecting New Data
-------------------

A flowchart to help guide you can be found [here](docs/new_indicator.png)

### Gather Requirements

- What pages will this be displayed?
- How will this be aggregated?
- Is this a property that is set and never changes, or a property that changes over time?
- How is this set in the app?
- What filters will be applied to this data?

### Collecting data

All data should be collected via a UCR data source.
Document lookups in these UCRs should be avoided as they increase processing time and related case changes are not picked up correctly
Location lookups are often necessary and ok. Use `ancestor_location` to ensure that there is only one database lookup.
If you absolutely need one, it should be a custom expression and heavily cached.

First look to see if a data source exists for the data you want to track.
If a data source does exist, add the appropriate column to the data source as a nullable column and rebuild the data source in place.
If an appropriate data source does not exist, create one in the dashboard UCR folder.

New UCRs should have the following data:
- Associated case or AWC id
- Supervisor/Sector id (if sharding the data source with Citus)
- timeEnd (Only for forms. Tables should be partitioned on this attribute)
- received_on (Only for forms)
- data points from the app to be collected

### Aggregating the data

If you're collecting data from a form, the first step is to aggregate the form data per case id or awc id into a table specifically for that form.
e.g. `icds_dashboard_growth_monitoring_forms`.
If you're collecting data from a case, it can be used in the initial setup where appropriate.
e.g. when collecting ccs_record data it can be inserted with the initial query for ccs_record_monthly
Then insert this data into the appropriate monthly table.
If necessary, pass it through to the next tables in the work flow (such as child_health information to agg_awc)

### Other Notes

- Don't look up other documents in a UCR
- Only collect raw data in the UCR. Use as few expressions in the UCR as possible.
- Keep the same names as the app as far as possible into the aggregation.
  It's very confusing when properties change between tables such as sex changing to gender.
- Prefer small_integer when possible and always use small_boolean instead of boolean
- When recording a property that can have multiple results, prefer an enumeration (using switch) instead of storing the raw value

Rebuilding UCR Data Sources
---------------------------

### Steps

1. Make changes to the UCR data source
   - Always add nullable columns so that the rebuilds can be done without deleting the table first
2. Kick off a rebuild using ./manage.py async_rebuild_table
   - This uses celery queues to rebuild the table so that the rebuild is parallelized
3. Monitor rebuild with "Asynchronous UCR Dashboard" in datadog

### Estimating Time to Rebuild

This is to give a small idea of how long a rebuild will take.
These should be periodically reviewed and updated as they will change as the project scales and improvements to scale data sources are added.

#### Important variables

- Number of forms/cases to be rebuilt
- Time it takes for one doc to be processed
  - Data sources without extra document lookups will be faster
  - Forms and cases likely have different times to process by default because forms also need to fetch from riak, but no current data on what that difference is
- Number of "ucr_indicator_queue"s we have deployed
- Size of current table/indexes
  - Theoretically larger tables and tables with more indexes are more expensive to insert to. We haven't done any performance tests on this
  - Can use table partitioning to solve this
- Other concurrent rebuilds
  - Currently the monthly tables for child_health and ccs_record are in the same queues and will take some processing as well

#### Basic formula

(number of forms/cases) * (doc processing time) / (number of queues)

#### Data

Currently number of queues on ICDS is 79

| Data Source Table | Per Doc Processing | Estimate of number of documents |
| --- | --- | --- |
| child_health monthly | 1.5 s | 100 per AWC |
| ccs_record monthly | 1.5 s | 50 per AWC |
| Complementary Feeding/PNC forms | 0.25 s | |

The complementary feeding and PNC forms should give a good baseline for documents we haven't rebuilt before, as they have few related documents.

Metrics to follow/tradeoff
--------------------------
Processing time

UCR query time

Dashboard query time


Aggregation task
----------------

To perform our large aggregation task we use [Airflow](https://airflow.apache.org/).
Airflow is a workflow management system that allows us to specify dependencies between tasks and schedule each task appropriately.
Our configuration of our workflow is stored in https://github.com/dimagi/pipes.
That repository only stores information about the workflow.
The queries and commands being run are stored as part of this repository.


## Running only one month

Currently this must be done manually.
To run one month, you must access the [airflow server](http://100.71.188.10:8080/admin/) (behind the VPN),
go to the dashboard aggregation, click "previous month" and select "mark success".

## Aggregation running slowly

Airflow collects some metrics that show the history of a task.
If you are unfamiliar with how long a task is expected to run, then you can view the history of the task by looking at the "task duration" tab.
Once you find the task(s) that have slowed, you should check if the query was blocked by another.
If you find that the query could not acquire the appropriate lock, reference the below troubleshooting section about locks.
Otherwise reference the slow query section in troubleshooting.

## Errors

Currently any errors are emailed to the dashboard aggregation email group.
The emails contain information such as the aggregation step that failed and a link to the log output of the task.


Troubleshooting
---------------

Connect to ICDS database: `./manage dbshell --database icds-ucr`

## Slow Queries

Find the current longest running queries: `select pid, query_start, query from pg_stat_activity order by query_start limit 10`

`EXPLAIN (statement)` should be the first step to understanding a slow query.
An official introduction into explain can be found in postgres's docs https://www.postgresql.org/docs/11/using-explain.html.
There can be a lot of information to understand when looking at your first queries.
A good rule of thumb is to take note of the estimated total costs displayed and begin looking at the inner most operations.
From the innermost operation, take one step out at a time and find where you see the largest cost increases.
The largest cost increase is a good place to begin looking to optimize your query.

Another issue we've seen before is Disk IO contention.
We run many tasks in parallel and therefore there may be too many tasks running at one time and using much of the disk.
You can look at the "Postgres - Overview" DataDog dashboard to see if IO wait or disk queue size is very high during the task

Note that while its largely the same, there are differences in tuning Citus queries vs postgres queries.
[Citus docs](http://docs.citusdata.com/en/v8.3/performance/performance_tuning.html) provide an overview of tuning both.

## Locking queries

We log the number of locked queries to datadog under `postgresql.locks.not_granted`.
There is a graph of this on our Postgres - Overview dashboard.

For more specific troubleshooting for each lock that is currently occurring on the database:

Find locks that haven't been granted: `SELECT * FROM pg_locks WHERE NOT GRANTED`
Queries that are blocked on a lock:
`SELECT query_start, query FROM pg_locks, pg_stat_activity WHERE pg_locks.pid = pg_stat_activity.pid AND NOT granted`

Depending on the type of lock acquired (`pg_locks.locktype`), you can adjust your query to find the query that's blocking.
For example if `locktype` is `virtualxid`, you can run `SELECT * FROM pg_locks WHERE virtualxid = 'xid' AND GRANTED` to find the process(s) that currently have the lock acquired.

More specifically for finding distributed Citus locks:

```sql
WITH citus_xacts AS (
  SELECT * FROM get_all_active_transactions() WHERE initiator_node_identifier = 0
),
citus_wait_pids AS (
  SELECT
    (SELECT process_id FROM citus_xacts WHERE transaction_number = waiting_transaction_num) AS waiting_pid,
    (SELECT process_id FROM citus_xacts WHERE transaction_number = blocking_transaction_num) AS blocking_pid
  FROM
    dump_global_wait_edges()
)
SELECT
  waiting_pid AS blocked_pid,
  blocking_pid,
  waiting.query AS blocked_statement,
  blocking.query AS current_statement_in_blocking_process
FROM
  citus_wait_pids
JOIN
  pg_stat_activity waiting ON (waiting_pid = waiting.pid)
JOIN
  pg_stat_activity blocking ON (blocking_pid = blocking.pid)
```

More about locks:
* https://www.citusdata.com/blog/2018/02/15/when-postgresql-blocks/
* https://www.citusdata.com/blog/2018/02/22/seven-tips-for-dealing-with-postgres-locks/

## Killing queries

Killing a query should be done with `SELECT pg_cancel_backend(pid)` when possible.
If that doesn't work `SELECT pg_terminate_backend(pid)` probably will.
The difference is cancel is SIGTERM and terminate is SIGKILL described in more detail [here](https://www.postgresql.org/docs/current/server-shutdown.html)

## Reducing load on the database

Stopping all ucr_indicator_queue to reduce load: `cchq icds celery stop --only ucr_indicator_queue`

Stopping pillows: `cchq icds pillowtop stop`


Useful references
-----------------

Postgres documentation: https://www.postgresql.org/docs/11/index.html
Citus documentation: https://docs.citusdata.com/en/v8.3/index.html
