# Setup Test Data

To populate test data for any domain, you could simply do a bulk upload for cases with the following columns
1. case_id: Blank for new cases
2. name: (Optional) Add a name for each case. Remove column if not using
3. gps_point: GPS coordinate for the case that has latitude, longitude, altitude and accuracy separated by an empty space. Example: `9.9999952 3.2859413 393.2 4.36`. This is the case property saved on a case to capture its location and is configurable with default value being `gps_point`, so good to check Geospatial Configuration Settings page for the project to confirm the case property being used before doing the upload. If its different, then this column should use that case property instead of `gps_point`
4. owner_name: (Optional) To assign case to a mobile worker, simply add worker username here. Remove column if not using

For dimagi devs looking for bulk data, you could use any of the excel sheets available in https://dimagi-dev.atlassian.net/browse/SC-3051

# Case Grouping

There are various configuration settings available for deciding how case grouping is done. These parameters are saved in the `GeoConfig` model which is linked to a domain.
It is important to note however, that not all available parameters will be used for case grouping. The parameters that actually get used is determined by the chosen grouping
method. Mainly, these are:
1. Min/Max Grouping - Grouping is done by specifying the minimum and maximum number of cases that each group may have.
2. Target Size Grouping - Grouping is done by specifying how many groups should be created. Cases will then evenly get distributed into groups to meet the target number of groups.
