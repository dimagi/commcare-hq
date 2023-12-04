Geospatial Features
===================

Geospatial features allow the management of cases and mobile workers
based on their geographical location. Case location is stored in a
configurable case property, which defaults to "gps_point". Mobile
worker location is stored in user data, also with the name "gps_point".


Case Grouping
-------------

There are various configuration settings available for deciding how case
grouping is done. These parameters are saved in the `GeoConfig` model
which is linked to a domain. It is important to note however, that not
all available parameters will be used for case grouping. The parameters
that actually get used is determined by the chosen grouping method.
Mainly, these are:

1. Min/Max Grouping - Grouping is done by specifying the minimum and
   maximum number of cases that each group may have.

2. Target Size Grouping - Grouping is done by specifying how many groups
   should be created. Cases will then evenly get distributed into groups
   to meet the target number of groups.


CaseGroupingReport pagination
-----------------------------

The `CaseGroupingReport` class uses Elasticsearch
[GeoHash Grid Aggregation][1] to group cases into buckets.

Elasticsearch [bucket aggregations][2] create buckets of documents,
where each bucket corresponds to a property that determines whether a
document falls into that bucket.

The buckets of GeoHash Grid Aggregation are cells in a grid. Each cell
has a GeoHash, which is like a ZIP code or a postal code, in that it
represents a geographical area. If a document's GeoPoint is in a
GeoHash's geographical area, then Elasticsearch places it in the
corresponding bucket. For more information on GeoHash grid cells, see
the Elasticsearch docs on [GeoHash cell dimensions][3].

GeoHash Grid Aggregation buckets look like this:
```
[
    {
        "key": "u17",
        "doc_count": 3
    },
    {
        "key": "u09",
        "doc_count": 2
    },
    {
        "key": "u15",
        "doc_count": 1
    }
]
```
In this example, "key" is a GeoHash of length 3, and "doc_count" gives
the number of documents in each bucket, or GeoHash grid cell.

For `CaseGroupingReport`, buckets are pages. So pagination simply flips
from one bucket to the next.


Setting Up Test Data
--------------------

To populate test data for any domain, you could simply do a bulk upload
for cases with the following columns

1. case_id: Blank for new cases

2. name: (Optional) Add a name for each case. Remove column if not using

3. gps_point: GPS coordinate for the case that has latitude, longitude,
   altitude and accuracy separated by an empty space. Example:
   `9.9999952 3.2859413 393.2 4.36`. This is the case property saved on
   a case to capture its location and is configurable with default
   value being `gps_point`, so good to check Geospatial Configuration
   Settings page for the project to confirm the case property being
   used before doing the upload. If its different, then this column
   should use that case property instead of `gps_point`

4. owner_name: (Optional) To assign case to a mobile worker, simply add
   worker username here. Remove column if not using.

For Dimagi devs looking for bulk data, you could use any of the Excel
sheets available in Jira ticket [SC-3051][4].


[1]: https://www.elastic.co/guide/en/elasticsearch/reference/5.6/search-aggregations-bucket-geohashgrid-aggregation.html
[2]: https://www.elastic.co/guide/en/elasticsearch/reference/5.6/search-aggregations-bucket.html
[3]: https://www.elastic.co/guide/en/elasticsearch/reference/5.6/search-aggregations-bucket-geohashgrid-aggregation.html#_cell_dimensions_at_the_equator
[4]: https://dimagi-dev.atlassian.net/browse/SC-3051
