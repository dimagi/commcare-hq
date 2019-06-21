ICDS Dashboard
==============

Information for the custom ICDS reporting dashboard. It can be accessed at \<url\>/a/\<domain\>/icds_dashboard.
Currently it's only possible for one domain on each environment to access this dashboard,
so only test locally and don't add random domains to the feature flag

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
- State id
- timeEnd (Only for forms. Tables should be partitioned on this attribute)
- received_on (Only for forms)
- data points from the app to be collected

### Aggregating the data

The work flow shown in the following picture is the eventual ideal,
and there is ongoing work to make all of the aggregation follow [this pattern](docs/goal_state_aggregation.png)

Currently Complementary Feeding Forms follows this work flow if you want an example.

If you're collecting data from a form, the first step is to aggregate the data per case id or awc id.
Then insert this data into the appropriate monthly table.
If necessary, pass it through to the next tables in the work flow (such as child_health information to agg_awc)

Think through the performance of your additions to this script. Previous mistakes:

- https://github.com/dimagi/commcare-hq/pull/19924

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

Extracting forms references from case UCR data sources
------------------------------------------------------

### Steps

1. Identify form xmlns to be extracted from either (or both) child_health or ccs_record tableau data sources
2. Create a UCR data source for that form to collect the raw data necessary [Example here](https://github.com/dimagi/commcare-hq/blob/f19872d54fe482e130cdcf0f0c7e83eb1c894072/custom/icds_reports/ucr/data_sources/dashboard/postnatal_care_forms.json)
3. Add tests using forms from the QA domain (icds-dashboard-qa on india) [Example here](https://github.com/dimagi/commcare-hq/blob/f19872d54fe482e130cdcf0f0c7e83eb1c894072/custom/icds_reports/ucr/tests/test_pnc_form_ucr.py)
4. Add a model that will follow the same format as the tableau data sources (unique for case_id and month) [Example Here](https://github.com/dimagi/commcare-hq/blob/f19872d54fe482e130cdcf0f0c7e83eb1c894072/custom/icds_reports/models.py#L665-L725)
5. Create an aggregation helper that will take data from the UCR data source and insert it into the aggregate table [Example Here](https://github.com/dimagi/commcare-hq/blob/f19872d54fe482e130cdcf0f0c7e83eb1c894072/custom/icds_reports/utils/aggregation.py#L229-L315)
6. In that helper, write a query that compares it to the old data [Example Here](https://github.com/dimagi/commcare-hq/blob/f19872d54fe482e130cdcf0f0c7e83eb1c894072/custom/icds_reports/utils/aggregation.py#L317-L351)
7. PR & deploy this.
8. Build the UCR, likely using async_rebuild_table.
9. Aggregate the data using `aggregate` on the model.
10. Verify that the data is the same using `compare_with_old_data` on the model.
11. Change the aggregation script to use the new tables.
12. After some test time, remove the references to the old columns that you have replaced from the original tableau data source.

Metrics to follow/tradeoff
--------------------------
Processing time

UCR query time

Dashboard query time

Known areas that can be changed to improve performance
------------------------------------------------------
1. The aggregation step should be able to be split by state.
   These tasks can then be kicked off in parallel.
2. Caching of location lookups.
   Locations are mostly static so they can be cached quite heavily if we believe it's effective.
3. Moving to custom queries for some UCRs.

   Following up on [this PR](https://github.com/dimagi/commcare-hq/pull/20452) it could be useful experimenting with joins, multiple queries or SQL not supported in UCR reports.

   The highest ROI are moving reports based on ccs_record_monthly_v2, child_health_monthly_v2 and person_cases_v2 (in that order).

   The end goal being no longer needed either monthly UCR (queries only on the base case UCR & appropriate form UCR) and reducing the number of columns in person_cases_v2.
   
   As of March, 2019 we have rolled out person_cases_v3 which achieves the reduction in columns in person_case_v2.

4. Move to native postgres partitioning.

   Postgres 10 introduced a native partitioning feature that we could use.

   Postgres 11 will be adding some more features and performance improvements

   Currently the dashboard tables are manually partitioned by inserting directly into the partitioned tables and UCR data sources use triggers created by architect.
5. Reduce number of partitions on tables.

   Check constraints are processed linearly so having many partitions can negatively impact query times.

   Currently a new partition is created for every day in agg_awc_daily and every month 5 are created in agg_child_health & agg_ccs_record

   In postgres 11, this is less of an issue as the query planner can create better queries based on native partitioning
6. Make use of inserted_at and/or received on to intelligently update the tables
   Currently we loop over the previous month and fully delete are re-aggregate all data for the month.
7. Change the aggregation step to insert into temporary tables before dropping real table.

   This should reduce/eliminate any locking that is not needed and also remove any on disk inefficiency introduced by inserting then updating
8. Sort data before inserting into the aggregate table. Use BRIN indexes on those sorted columns
9. Include full location hierarchy in each table.

   Currently we join with a location table to get the location's name and full hierarchy. Testing this out may be useful
10. General postgres config updates.
11. Experiment with Foreign Data Wrappers

    a) Try out writing different UCR data sources to different databases and aggregating them on a separate dashboard database server

    b) Try out either moving old less accessed data to an older server or separating different state's data on different dashboard servers


Troubleshooting
---------------

Connect to ICDS database: `./manage dbshell --database icds-ucr`

Find longest running queries: `select pid, query_start, query from pg_stat_activity order by query_start limit 10`

Find locks that haven't been granted: `SELECT relation::regclass, * FROM pg_locks WHERE NOT GRANTED`

Killing a query should be done with `SELECT pg_cancel_backend(pid)` when possible.
If that doesn't work `SELECT pg_terminate_backend(pid)` probably will.
The difference is cancel is SIGTERM and terminate is SIGKILL described in more detail [here](https://www.postgresql.org/docs/current/server-shutdown.html)

Stopping all ucr_indicator_queue to reduce load: `cchq icds fab supervisorctl:"stop commcare-hq-icds-celery_ucr_indicator_queue_0"`

Purging all aggregation tasks from the queue: `./manage.py celery amqp queue.purge icds_aggregation_queue`

Restarting the aggregation *before doing this you should be certain that the aggregation is not running and will not start on its own*:

```python
from custom.icds_reports.tasks import move_ucr_data_into_aggregation_tables
from  dimagi.utils.couch.cache.cache_core import get_redis_client

# clear out the redis key used for @serial_task
client = get_redis_client()
client.delete('move_ucr_data_into_aggregation_tables-move-ucr-data-into-aggregate-tables')

# note that this defaults to current date from utcnow (usually what you want)
move_ucr_data_into_aggregation_tables.delay(intervals=1)
```
