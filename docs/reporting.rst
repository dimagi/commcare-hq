Reporting
=========

A report is
    a logical grouping of indicators with common config options (filters etc)

The way reports are produced in CommCare is still evolving so there are a number
of different frameworks and methods for generating reports. Some of these are
*legacy* frameworks and should not be used for any future reports.


Recommended approaches for building reports
-------------------------------------------

TODO: SQL reports, Elastic reports, Custom case lists / details,

Things to keep in mind:

* `report API <report_api>`_


* `Fluff`_
* `Ctable`_
* `sqlagg`_
* `couchdbkit-aggregate`_ (legacy)

.. _Ctable: https://github.com/dimagi/ctable
.. _sqlagg: https://github.com/dimagi/sql-agg
.. _couchdbkit-aggregate: https://github.com/dimagi/couchdbkit-aggregate
.. _sqlalchemy: http://docs.sqlalchemy.org/en/rel_0_8/core/tutorial.html

Example Custom Report Scaffolding
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    class MyBasicReport(GenericTabularReport, CustomProjectReport):
        name = "My Basic Report"
        slug = "my_basic_report"
        fields = ('corehq.apps.reports.filters.dates.DatespanFilter',)

        @property
        def headers(self):
            return DataTablesHeader(DataTablesColumn("Col A"),
                                    DataTablesColumnGroup(
                                        "Group 1",
                                        DataTablesColumn("Col B"),
                                        DataTablesColumn("Col C")),
                                    DataTablesColumn("Col D"))

        @property
        def rows(self):
            return [
                ['Row 1', 2, 3, 4],
                ['Row 2', 3, 2, 1]
            ]

Hooking up reports to CommCare HQ
---------------------------------

Custom reports can be configured in code or in the database. To configure custom reports in code
follow the following instructions.

First, you must add the app to `HQ_APPS` in `settings.py`.  It must have an `__init__.py` and a
`models.py` for django to recognize it as an app.

Next, add a mapping for your domain(s) to the custom reports module root to the `DOMAIN_MODULE_MAP`
variable in `settings.py`.

Finally, add a mapping to your custom reports to `__init__.py` in your custom reports submodule:

.. code-block:: python

    from myproject import reports

    CUSTOM_REPORTS = (
        ('Custom Reports', (
            reports.MyCustomReport,
            reports.AnotherCustomReport,
        )),
    )


.. _sql:

Reporting on data stored in SQL
-------------------------------

As described above there are various ways of getting reporting data into
and SQL database. From there we can query the data in a number of ways.

Extending the ``SqlData`` class
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``SqlData`` class allows you to define how to query the data
in a declarative manner by breaking down a query into a number of components.

.. autoclass:: corehq.apps.reports.sqlreport.SqlData
    :members: table_name, columns, filters, filter_values, group_by, keys

This approach means you don't write any raw SQL. It also allows you to
easily include or exclude columns, format column values and combine values
from different query columns into a single report column (e.g. calculate percentages).

In cases where some columns may have different filter values e.g. males vs females,
**sqlagg** will handle executing the different queries and combining the results.

This class also implements the ``corehq.apps.reports.api.ReportDataSource``.

See `Report API <report_api_>`_ and `sqlagg`_ for more info.

e.g.

.. code-block:: python

    class DemoReport(SqlTabularReport, CustomProjectReport):
        name = "SQL Demo"
        slug = "sql_demo"
        fields = ('corehq.apps.reports.filters.dates.DatespanFilter',)

        # The columns to include the the 'group by' clause
        group_by = ["user"]

        # The table to run the query against
        table_name = "user_report_data"

        @property
        def filters(self):
            return [
                BETWEEN('date', 'startdate', 'enddate'),
            ]

        @property
        def filter_values(self):
            return {
                "startdate": self.datespan.startdate_param_utc,
                "enddate": self.datespan.enddate_param_utc,
                "male": 'M',
                "female": 'F',
            }

        @property
        def keys(self):
            # would normally be loaded from couch
            return [["user1"], ["user2"], ['user3']]

        @property
        def columns(self):
            return [
                DatabaseColumn("Location", SimpleColumn("user_id"), format_fn=self.username),
                DatabaseColumn("Males", CountColumn("gender"), filters=self.filters+[EQ('gender', 'male')]),
                DatabaseColumn("Females", CountColumn("gender"), filters=self.filters+[EQ('gender', 'female')]),
                AggregateColumn(
                    "C as percent of D",
                    self.calc_percentage,
                    [SumColumn("indicator_c"), SumColumn("indicator_d")],
                    format_fn=self.format_percent)
            ]

        _usernames = {"user1": "Location1", "user2": "Location2", 'user3': "Location3"}  # normally loaded from couch
        def username(self, key):
            return self._usernames[key]

        def calc_percentage(num, denom):
            if isinstance(num, Number) and isinstance(denom, Number):
                if denom != 0:
                    return num * 100 / denom
                else:
                    return 0
            else:
                return None

        def format_percent(self, value):
            return format_datatables_data("%d%%" % value, value)


Using the `sqlalchemy`_ API directly
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TODO


.. _report_api:

Report API
----------
Part of the evolution of the reporting frameworks has been the development of
a *report api*. This is essentially just a change in the architecture of
reports to separate the data from the display. The data can be produced
in various formats but the most common is an list of dicts.

e.g.

.. code-block:: python

  data = [
    {
      'slug1': 'abc',
      'slug2': 2
    },
    {
      'slug1': 'def',
      'slug2': 1
    }
    ...
  ]

This is implemented by creating a report data source class that extends
``corehq.apps.reports.api.ReportDataSource`` and overriding the
:func:`get_data` function.

.. autoclass:: corehq.apps.reports.api.ReportDataSource
    :members: slugs, get_data

These data sources can then be used independently or the CommCare reporting
user interface and can also be reused for multiple use cases such as
displaying the data in the CommCare UI as a table, displaying it in a map,
making it available via HTTP etc.

An extension of this base data source class is the ``corehq.apps.reports.sqlreport.SqlData``
class which simplifies creating data sources that get data by running
an SQL query. See section on `SQL reporting <sql_>`_ for more info.

e.g.

.. code-block:: python

  class CustomReportDataSource(ReportDataSource):
      def get_data(self):
          startdate = self.config['start']
          enddate = self.config['end']

          ...

          return data

  config = {'start': date(2013, 1, 1), 'end': date(2013, 5, 1)}
  ds = CustomReportDataSource(config)
  data = ds.get_data()

.. _dynamic_reports:

Adding dynamic reports
----------------------

Domains support dynamic reports. Currently the only verison of these are maps reports.
There is currently no documentation for how to use maps reports. However you can look
at the `drew` or `aaharsneha` domains on prod for examples.

.. _Fluff:

How pillow/fluff work
---------------------

`GitHub <https://github.com/dimagi/fluff>`_

Note: This should be rewritten, I wrote it when I was first trying to understand
how fluff works.

A Pillow provides the ability to listen to a database, and on changes, the class
`BasicPillow` calls change_transform and passes it the changed doc dict.  This
method can process the dict and transform it, or not.  The result is then
passed to the method ``change_transport``, which must be implemented in any
subclass of ``BasicPillow``.  This method is responsible for acting upon the
changes.

In fluff's case, it stores an indicator document with some data calculated from
a particular type of doc.  When a relevant doc is updated, the calculations are
performed.  The diff between the old and new indicator docs is calculated, and
sent to the db to update the indicator doc.

fluff's `Calculator` object auto-detects all methods that are decorated by
subclasses of `base_emitter` and stores them in a `_fluff_emitters` array.
This is used by the `calculate` method to return a dict of emitter slugs mapped
to the result of the emitter function (called with the newly updated doc)
coerced to a list.

to rephrase:  fluff emitters accept a doc and return a generator where each
element corresponds to a contribution to the indicator
