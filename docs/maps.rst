==========
Reporting: Maps in HQ
==========

What is the "Maps Report"?
==========================

We now have map-based reports in HQ.
The "maps report" is not really a report, in the sense that it does not query or calculate any data on its own.
Rather, it's a generic front-end visualization tool that consumes data from some other place... other places such as another (tabular) report, or case/form data (work in progress).

To create a map-based report, you must configure the `map report template`_ with specific parameters.
These are:

.. _map report template: https://github.com/dimagi/commcare-hq/blob/8af9177910fa3ae5642a68d8085071e91c1356f6/corehq/apps/reports/standard/inspect.py#L685

* the backend data source which will power the report (required)
* customizations to the display/behavior of the map itself (optional, but suggested for anything other than quick prototyping)

There are two options for how this configuration actually takes place:

* via a domain's "dynamic reports", where you can create specific configurations of a generic report for a domain. (TODO: document this separately)
* subclass the map report to provide/generate the config parameters.
  You should **not** need to subclass any code functionality.
  This is useful for making a more permanent map configuration, and when the configuration needs to be dynamically generated based on other data or domain config (e.g., for `CommTrack`_)

.. _CommTrack: https://github.com/dimagi/commcare-hq/blob/8af9177910fa3ae5642a68d8085071e91c1356f6/corehq/apps/reports/commtrack/maps.py#L7

Orientation
===========

Abstractly, the map report consumes a table of data from some source.
Each row of the table is a geographical feature (point or region).
One column is identified as containing the geographical data for the feature.
All other columns are arbitrary attributes of that feature that can be visualized on the map.
Another column may indicate the name of the feature.

The map report contains, obviously, a map.
Features are displayed on the map, and may be styled in a number of ways based on feature attributes.
The map also contains a legend generated for the current styling.
Below the map is a table showing the raw data.
Clicking on a feature or its corresponding row in the table will open a detail popup.
The columns shown in the table and the detail popup can be customized.

Attribute data is generally treated as either being numeric data or enumerated data (i.e., belonging to a number of discrete categories).
Strings are inherently treated as enum data.
Numeric data can be treated as enum data be specifying thresholds: numbers will be mapped to enum 'buckets' between consecutive thresholds (e.g, thresholds of ``10``, ``20`` will create enum categories: ``< 10``, ``10-20``, ``> 20``).

Styling
=======

Different aspects of a feature's marker on the map can be styled based on its attributes.
Currently supported visualizations (you may see these referred to in the code as "display axes" or "display dimensions") are:

* varying the size (numeric data only)
* varying the color/intensity (numeric data (color scale) or enum data (fixed color palette))
* selecting an icon (enum data only)

Size and color may be used concurrently, so one attribute could vary size while another varies the color... this is useful when the size represents an absolute magnitude (e.g., # of pregnancies) while the color represents a ratio (% with complications).
Region features (as opposed to point features) only support varying color.

A particular configuration of visualizations (which attributes are mapped to which display axes, and associated styling like scaling, colors, icons, thresholds, etc.) is called a `metric`.
A map report can be configured with many different metrics.
The user selects one metric at a time for viewing.
*Metrics may not correspond to table columns one-to-one*, as a single column may be visualized multiple ways, or in combination with other columns, or not at all (shown in detail popup only).
If no metrics are specified, they will be auto-generated from best guesses based on the available columns and data feeding the report.

There are several sample reports that comprehensively demo the potential styling options:

* `Demo 1`_
* `Demo 2`_

.. _Demo 1: https://www.commcarehq.org/a/commtrack-public-demo/reports/maps_demo/
.. _Demo 2: https://www.commcarehq.org/a/commtrack-public-demo/reports/maps_demo2/

Data Sources
============

Any report filters in the map report are passed on verbatim to the backing data source.

One column of the returned data must be the geodata. For point features, this can be in the format of a geopoint xform question (e.g, ``42.366 -71.104``). The geodata format for region features is outside the scope of the document.

``report``
----------

Retrieve data from a ``ReportDataSource`` (the abstract data provider of Simon's new reporting framework -- TODO: link to this documentation)

``legacyreport``
----------------

Retrieve data from a ``GenericTabularReport`` which has not yet been refactored to use Simon's new framework.
*Not ideal* and should only be used for backwards compatibility.
Tabular reports tend to return pre-formatted data, while the maps report works best with raw data (for example, it won't know ``4%`` or ``30 mg`` are numeric data, and will instead treat them as text enum values). `Read more`_.

``csv`` and ``geojson``
-----------------------

Retrieve static data from a csv or geojson file on the server (only useful for testing/demo-- this powers the demo reports, for example).

.. _Read more:

Raw vs. Formatted Data
======================

Consider the difference between raw and formatted data.
Numbers may be formatted for readability (``12,345,678``, ``62.5%``, ``27 units``); enums may be converted to human-friendly captions; null values may be represented as ``--`` or ``n/a``.
The maps report works best when it has the raw data and can perform these conversions itself.
The main reason is so that it may generate useful legends, which requires the ability to appropriately format values that may never appear in the report data itself.

There are three scenarios of how a data source may provide data:

* *(worst)* only provide formatted data

  Maps report cannot distinguish numbers from strings from nulls.
  Data visualizations will not be useful.

* *(sub-optimal)* provide both raw and formatted data (most likely via the ``legacyreport`` adapter)

  Formatted data will be shown to the user, but maps report will not know how to format data for display in legends, nor will it know all possible values for an enum field -- only those that appear in the data.

* *(best)* provide raw data, and explicitly define enum lists and formatting functions in the report config
 
