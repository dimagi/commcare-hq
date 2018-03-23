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


Collecting New Data
-------------------

### Gather Requirements

- What pages will this be displayed?
- How will this be aggregated?
- Is this a property that is set and never changes, or a property that changes over time?
- How is this set in the app?
- What filters will be applied to this data?

### Collecting data

All data should be collected via a UCR data source.
Document lookups in these UCRs are effectively banned.
Location lookups are often necessary and ok. Use `ancestor_location`
If you absolutely need one, it should be a custom expression and heavily cached.

First look to see if a data source exists for the data you want to track.
If a data source does exist, add the appropriate column to the data source as a nullable column and rebuild the data source in place.
If an appropriate data source does not exist, create one in the dashboard UCR folder.

New UCRs should have the following data:
- Associated case or AWC id
- State id
- timeEnd (Only for forms. Tables should be partitioned on this attribute)
- data points from the app to be collected

### Aggregating the data

The work flow shown in the picture is the eventual ideal,
and there is ongoing work to make all of the aggregation follow [this pattern](doc/ideal_aggregation_workflow.png)

Currently Complementary Feeding Forms follows this work flow if you want an example.

If you're collecting data from a form, the first step is to aggregate the data per case id or awc id.
Then insert this data into the appropriate monthly table.
If necessary, pass it through to the next tables in the work flow (such as child_health information to agg_awc)

Think through the performance of your additions to this script. Previous mistakes:

- https://github.com/dimagi/commcare-hq/pull/19924

### Other Notes

- Don't look up other documents in a UCR
- Only collect raw data in the UCR. Use as few expressions in the UCR as possible.
- Keep the same names as the app as far as possible into the aggregation. It's very confusing when sex changes to gender...
- Prefer small_int when possible and always use small_boolean instead of boolean

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
