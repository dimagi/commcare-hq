ICDS Dashboard
==============

Information for the custom ICDS reporting dashboard. It can be accessed at \<url\>/a/\<domain\>/icds_dashboard.
Currently it's only possible for one domain on each environment to access this dashboard,
so only test locally and don't add random domains to the feature flag

Rebuilding UCR Data Sources
---------------------------

## Steps

1. Make changes to the UCR data source
   - Always add nullable columns so that the rebuilds can be done without deleting the table first
2. Kick off a rebuild using ./manage.py async_rebuild_table
   - This uses celery queues to rebuild the table so that the rebuild is parallelized
3. Monitor rebuild with "Asynchronous UCR Dashboard" in datadog

## Estimating Time to Rebuild

This is to give a small idea of how long a rebuild will take.
These should be periodically reviewed and updated as they will change as the project scales and improvements to scale data sources are added.

### Important variables

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

### Basic formula

(number of forms/cases) * (doc processing time) / (number of queues)

### Data

Currently number of queues on ICDS is 79

| Data Source Table | Per Doc Processing | Estimate of number of documents |
| --- | --- | --- |
| child_health monthly | 1.5 s | 100 per AWC |
| ccs_record monthly | 1.5 s | 50 per AWC |
| Complementary Feeding/PNC forms | 0.25 s | |

The complementary feeding and PNC forms should give a good baseline for documents we haven't rebuilt before, as they have few related documents.
