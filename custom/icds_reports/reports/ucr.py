from __future__ import absolute_import
from __future__ import unicode_literals

from collections import OrderedDict
from memoized import memoized
from sqlalchemy.sql import func

from corehq.apps.userreports.custom.data_source import ConfigurableReportCustomQueryProvider


class MPR2APersonCases(ConfigurableReportCustomQueryProvider):
    """Simplified query:

    SELECT owner_id,
           COUNT(*) FILTER WHERE (sex=X AND resident=Y AND age_death=Z) AS dead_X_Y_Z_count
    FROM ucr_table
    WHERE (location_id = A & date_death > B)
    GROUP BY owner_id

    Reasons this is needed:
      - UCR does not support FILTER WHERE clause in select
    """
    def __init__(self, report_data_source):
        self.report_data_source = report_data_source
        self.helper = self.report_data_source.helper

    @property
    def table(self):
        return self.helper.get_table()

    @property
    @memoized
    def _age_in_days_at_death(self):
        return (self.table.c.date_death - self.table.c.dob)

    def _count_filter_aggregate_expr(self, column, label):
        return (func.count(self.table.c.doc_id).filter(column).label(label))

    def _column_helper(self, x, y, z=None):
        columns = self.table.c
        # These first two filters could be added to the where clause, but we
        # also want to show owner_ids without any dead/closed cases
        # Could likely be made more efficient with a subquery
        # Note that for mobile reports date_death is always included in the filter anyways
        column = (columns.closed_on != None) & (columns.date_death != None)  # noqa: E711
        column &= {
            "F": columns.sex == "F",
            "M": columns.sex == "M",
            "preg": (columns.female_death_type == "pregnant"),
            "del": (columns.female_death_type == "delivery"),
            "pnc": (columns.female_death_type == "pnc"),
        }[x]
        column &= {
            "resident": columns.resident == "yes",
            "migrant": columns.resident != "yes",
        }[y]

        if z is None:
            return self._count_filter_aggregate_expr(column, "dead_{}_{}_count".format(x, y))

        column &= {
            "neo": self._age_in_days_at_death <= 28,
            "postneo": self._age_in_days_at_death.between(29, 364),
            "child": self._age_in_days_at_death.between(365, 1826),
            "adult": columns.age_at_death_yrs >= 11,
        }[z]

        return self._count_filter_aggregate_expr(column, "dead_{}_{}_{}_count".format(x, y, z))

    def _columns(self, total_row=False):
        columns = (
            self._column_helper("F", "resident", "neo"),
            self._column_helper("M", "resident", "neo"),
            self._column_helper("F", "migrant", "neo"),
            self._column_helper("M", "migrant", "neo"),
            self._column_helper("F", "resident", "postneo"),
            self._column_helper("M", "resident", "postneo"),
            self._column_helper("F", "migrant", "postneo"),
            self._column_helper("M", "migrant", "postneo"),
            self._column_helper("F", "resident", "child"),
            self._column_helper("M", "resident", "child"),
            self._column_helper("F", "migrant", "child"),
            self._column_helper("M", "migrant", "child"),
            self._column_helper("F", "migrant", "adult"),
            self._column_helper("F", "resident", "adult"),
            self._column_helper("preg", "resident"),
            self._column_helper("preg", "migrant"),
            self._column_helper("del", "resident"),
            self._column_helper("del", "migrant"),
            self._column_helper("pnc", "resident"),
            self._column_helper("pnc", "migrant"),
        )

        if not total_row:
            columns = (self.table.c.owner_id.label("owner_id"),) + columns

        return columns

    def _get_query_object(self, report_data_source, total_row=False):
        filters = self.helper.sql_alchemy_filters
        filter_values = self.helper.sql_alchemy_filter_values
        query = (
            self.helper.adapter.session_helper.Session.query(
                *self._columns(total_row)
            )
            .filter(*filters)
            .params(filter_values)
        )
        if not total_row:
            query = query.group_by(self.table.c.owner_id)
        return query

    def get_data(self, start=None, limit=None):
        query_obj = self._get_query_object(self.report_data_source)
        if start:
            query_obj = query_obj.start(start)
        if limit:
            query_obj = query_obj.limit(limit)
        return OrderedDict([
            (r.owner_id, r._asdict())
            for r in query_obj.all()
        ])

    def get_total_row(self):
        query_obj = self._get_query_object(self.report_data_source, total_row=True)
        return ["Total"] + [r for r in query_obj.first()]

    def get_total_records(self):
        return self._get_query_object(self.report_data_source).count()
