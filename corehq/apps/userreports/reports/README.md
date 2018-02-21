Reports Overview
================

There are two main components involved in producing a report:

* the data source configuration
* the report configuration


The data source
---------------

The data source is usually a table in PostgreSQL, but data sources can also be ElasticSearch indexes.

A data source is defined in a DataSourceConfiguration instance. This determines where its data comes from (cases or forms), and how the data is filtered. The data source is populated by a background task. Data sources are not aggregated.


Report configurations
---------------------

Report configurations define queries on data sources. They are stored in ReportConfiguration instances.

Report configurations offer two kinds of filters:

* Default filters
* User filters

**User filters** offer the user the ability to filter report results themselves. This is usually for limiting results to a specific location, or date range, or mobile worker.

**Default filters** are applied first, and are transparent to end users; i.e. users who use the report will not be made aware that default filters have been applied before results are filtered by their user filters.

More than one report configuration can use the same data source configuration, but the Report Builder creates a new data source for each new report. (In the case of UCRs, default filters are a useful way to reuse data sources.)

Report configurations select columns from data source indicators. They can create new columns by aggregating data, or counting discrete values.

In report builder, "list" reports are not aggregated, and "summary" reports are. Report Builder limits aggregations to *average*, *sum* and *count*.


User-Configurable Reports
=========================

UCRs allow developers and TFMs/TPMs to define data sources and reports using JSON. You can find comprehensive documentation at corehq/apps/userreports/README.md


Report Builder
==============

Report Builder is a friendlier user interface for defining UCRs. Its emphasis is on usability, with a trade-off on report functionality.

The front end is built on the KnockoutJS framework.

You can find an overview of how the KnockoutJS ViewModel is populated at corehq/apps/userreports/reports/builder/README.md

The ViewModel itself is corehq/apps/userreports/static/userreports/js/builder_view_models.js

When the user opens Report Builder, and chooses whether their data comes from cases or forms, Django will create a temporary data source for the Report Builder preview. The data source includes columns for as many indicators as possible (with a maximum of 300 columns). The same data source is used for "list" reports and "summary" reports. It will be populated with up to 100 rows.

Every change the user makes in the interface will fetch an updated preview by running the current state of the report configuration against the data source, and redering the result as the final report would be rendered.
