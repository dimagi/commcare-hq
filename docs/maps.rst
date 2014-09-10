=====================
Reporting: Maps in HQ
=====================

What is the "Maps Report"?
==========================

We now have map-based reports in HQ.
The "maps report" is not really a report, in the sense that it does not query or calculate any data on its own.
Rather, it's a generic front-end visualization tool that consumes data from some other place... other places such as another (tabular) report, or case/form data (work in progress).

To create a map-based report, you must configure the `map report template`_ with specific parameters.
These are:

.. _map report template: https://github.com/dimagi/commcare-hq/blob/8af9177910fa3ae5642a68d8085071e91c1356f6/corehq/apps/reports/standard/inspect.py#L685

* ``data_source`` -- the backend data source which will power the report (required)
* ``display_config`` -- customizations to the display/behavior of the map itself (optional, but suggested for anything other than quick prototyping)

There are two options for how this configuration actually takes place:

* via a domain's "dynamic reports" (see :ref:`dynamic_reports`), where you can create specific configurations of a generic report for a domain
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

.. _styling:

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

See :ref:`display_config`

Data Sources
============

Set this config on the ``data_source`` property.
It should be a ``dict`` with the following properties:

* ``geo_column`` -- the column in the returned data that contains the geo point (default: ``"geo"``)
* ``adapter`` -- which data adapter to use (one of the choices below)
* extra arguments specific to each data adapter

Note that any report filters in the map report are passed on verbatim to the backing data source.

One column of the data returned by the data source must be the geodata (in ``geo_column``).
For point features, this can be in the format of a geopoint xform question (e.g, ``42.366 -71.104``).
The geodata format for region features is outside the scope of the document.

``report``
----------

Retrieve data from a ``ReportDataSource`` (the abstract data provider of Simon's new reporting framework -- see :ref:`report_api`)

Parameters:

* ``report`` -- fully qualified name of ``ReportDataSource`` class
* ``report_params`` -- ``dict`` of static config parameters for the ``ReportDataSource`` (optional)

``legacyreport``
----------------

Retrieve data from a ``GenericTabularReport`` which has not yet been refactored to use Simon's new framework.
*Not ideal* and should only be used for backwards compatibility.
Tabular reports tend to return pre-formatted data, while the maps report works best with raw data (for example, it won't know ``4%`` or ``30 mg`` are numeric data, and will instead treat them as text enum values). `Read more`_.

Parameters:

* ``report`` -- fully qualified name of tabular report view class (descends from ``GenericTabularReport``)
* ``report_params`` -- ``dict`` of static config parameters for the ``ReportDataSource`` (optional)

``case``
--------

Pull case data similar to the Case List.

*(In the current implementation, you must use the same report filters as on the regular Case List report)*

Parameters:

* ``geo_fetch`` -- a mapping of case types to directives of how to pull geo data for a case of that type. Supported directives:

  - name of case property containing the ``geopoint`` data
  - ``"link:xxx"`` where ``xxx`` is the case type of a linked case; the adapter will then serach that linked case for geo-data based on the directive of the linked case type *(not supported yet)*

  In the absence of any directive, the adapter will first search any linked ``Location`` record *(not supported yet)*, then try the ``gps`` case property.

``csv`` and ``geojson``
-----------------------

Retrieve static data from a csv or geojson file on the server (only useful for testing/demo-- this powers the demo reports, for example).

.. _display_config:

Display Configuration
=====================

Set this config on the ``display_config`` property.
It should be a ``dict`` with the following properties:

*(Whenever 'column' is mentioned, it refers to a column slug as returned by the data adapter)*

**All properties are optional. The map will attempt sensible defaults.**

* ``name_column`` -- column containing the name of the row; used as the header of the detail popup

* ``column_titles`` -- a mapping of columns to display titles for each column

* ``detail_columns`` -- a list of columns to display in the detail popup

* ``table_columns`` -- a list of columns to display in the data table below the map

* ``enum_captions`` -- display captions for enumerated values.
  A ``dict`` where each key is a column and each value is another ``dict`` mapping enum values to display captions.
  These enum values reflect the results of any transformations from ``metrics`` (including ``_other``, ``_null``, and ``-``).

* ``numeric_format`` -- a mapping of columns to functions that apply the appropriate numerical formatting for that column.
  Expressed as the body of a function that returns the formatted value (``return`` statement required!).
  The unformatted value is passed to the function as the variable ``x``.

* ``detail_template`` -- an underscore.js template to format the content of the detail popup

* ``metrics`` -- define visualization metrics (see :ref:`styling`).
  An array of metrics, where each metric is a ``dict`` like so:

  - ``auto`` -- column.
    Auto-generate a metric for this column with no additional manual input.
    Uses heuristics to determine best presentation format.

  *OR*

  - ``title`` -- metric title in sidebar (optional)

  *AND one of the following for each visualization property you want to control*

  - ``size`` (static) -- set the size of the marker (radius in pixels)

  - ``size`` (dynamic) -- vary the size of the marker dynamically.
    A dict in the format:

    - ``column`` -- column whose data to vary by

    - ``baseline`` -- value that should correspond to a marker radius of 10px

    - ``min`` -- min marker radius (optional)

    - ``max`` -- max marker radius (optional)

  - ``color`` (static) -- set the marker color (css color value)

  - ``color`` (dynamic) -- vary the color of the marker dynamically.
    A dict in the format:

    - ``column`` -- column whose data to vary by

    - ``categories`` -- for enumerated data; a mapping of enum values to css color values.
      Mapping key may also be one of these magic values:

      - ``_other``: a catch-all for any value not specified

      - ``_null``: matches rows whose value is blank; if absent, such rows will be hidden

    - ``colorstops`` -- for numeric data.
      Creates a sliding color scale.
      An array of colorstops, each of the format ``[<value>, <css color>]``.

    - ``thresholds`` -- (optional) a helper to convert numerical data into enum data via "buckets".
      Specify a list of thresholds.
      Each bucket comprises a range from one threshold up to but not including the next threshold.
      Values are mapped to the bucket whose range they lie in.
      The "name" (i.e., enum value) of a bucket is its lower threshold.
      Values below the lowest threshold are mapped to a special bucket called ``"-"``.

  - ``icon`` (static) -- set the marker icon (image url)

  - ``icon`` (dynamic) -- vary the icon of the marker dynamically.
    A dict in the format:

    - ``column`` -- column whose data to vary by

    - ``categories`` -- as in ``color``, a mapping of enum values to icon urls

    - ``thresholds`` -- as in ``color``

  ``size`` and ``color`` may be combined (such as one column controlling size while another controls the color).
  ``icon`` must be used on its own.

  For date columns, any relevant number in the above config (``thresholds``, ``colorstops``, etc.) may be replaced with a date (in ISO format).

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
 
