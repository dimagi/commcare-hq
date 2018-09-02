from __future__ import absolute_import
from __future__ import unicode_literals

from collections import OrderedDict

from memoized import memoized
import sqlalchemy
from sqlalchemy.sql import func

from corehq.sql_db.connections import connection_manager
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
            "migrant": columns.resident.is_distinct_from("yes"),
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


session_helper = connection_manager.get_session_helper('icds-ucr')
metadata = sqlalchemy.MetaData(bind=session_helper.engine)

ChildHealthMonthlyViewAlchemy = sqlalchemy.Table(
    'child_health_monthly_view', metadata, autoload=True
)


class ChildHealthMonthlyUCR(ConfigurableReportCustomQueryProvider):
    """
    Reasons these are needed:
      - UCR needs to combine form data with case data
    """

    def __init__(self, report_data_source):
        self.report_data_source = report_data_source
        self.helper = self.report_data_source.helper
        self.helper.set_table(ChildHealthMonthlyViewAlchemy)

    @property
    def table(self):
        return ChildHealthMonthlyViewAlchemy

    def get_data(self, start=None, limit=None):
        query_obj = self._get_query_object()
        if start:
            query_obj = query_obj.start(start)
        if limit:
            query_obj = query_obj.limit(limit)
        return OrderedDict([
            (r.awc_id, r._asdict())
            for r in query_obj.all()
        ])

    def get_total_row(self):
        query_obj = self._get_query_object(total_row=True)
        return ["Total"] + [r for r in query_obj.first()]

    def get_total_records(self):
        return self._get_query_object().count()


class MPR6bChildHealth(ChildHealthMonthlyUCR):
    def _column_helper(self, sex):
        return func.sum(self.table.c.pse_days_attended).filter(
            self.table.c.sex == sex
        )

    def _columns(self, total_row=False):
        columns = (
            self._column_helper('M').label('pse_daily_attendance_male'),
            self._column_helper('F').label('pse_daily_attendance_female'),
        )
        if not total_row:
            columns = (self.table.c.awc_id.label("awc_id"),) + columns
        return columns

    def _get_query_object(self, total_row=False):
        filters = self.helper.sql_alchemy_filters
        filter_values = self.helper.sql_alchemy_filter_values
        query = (
            self.helper.adapter.session_helper.Session.query(
                *self._columns(total_row)
            )
            .filter(*filters)
            .filter(self.table.c.pse_eligible == 1)
            .params(filter_values)
        )
        if not total_row:
            query = query.group_by(self.table.c.awc_id)
        return query


class MPR6acChildHealth(ChildHealthMonthlyUCR):
    def _column_helper(self, pse, gender, other=None):
        columns = self.table.c
        column = (columns.pse_eligible == 1)
        column &= {
            '16_days': columns.pse_days_attended >= 16,
            'absent': columns.pse_days_attended.in_((0, None)),
            'partial': columns.pse_days_attended.between(1, 15)
        }[pse]
        column &= {
            'male': columns.sex == 'M',
            'female': columns.sex == 'F',
        }[gender]
        if other is None:
            return func.count(self.table.c.case_id).filter(column).label("pse_{}_{}".format(pse, gender))

        column &= {
            'st': columns.caste == 'st',
            'sc': columns.caste == 'sc',
            'others': columns.caste.notin_(('st', 'sc')),
            'disabled': columns.disabled == '1',
            'minority': columns.minority == '1',
        }[other]
        return func.count(self.table.c.case_id).filter(column).label("pse_{}_{}_{}".format(pse, gender, other))

    def _columns(self, total_row=False):
        columns = (
            self._column_helper("16_days", "male", "st"),
            self._column_helper("16_days", "female", "st"),
            self._column_helper("16_days", "male", "sc"),
            self._column_helper("16_days", "female", "sc"),
            self._column_helper("16_days", "male", "others"),
            self._column_helper("16_days", "female", "others"),
            self._column_helper("16_days", "male", "disabled"),
            self._column_helper("16_days", "female", "disabled"),
            self._column_helper("16_days", "male", "minority"),
            self._column_helper("16_days", "female", "minority"),
            self._column_helper("absent", "male"),
            self._column_helper("absent", "female"),
            self._column_helper("partial", "male"),
            self._column_helper("partial", "female"),
            func.count(self.table.c.case_id).filter(self.table.c.sex == 'M').label("child_count_male"),
            func.count(self.table.c.case_id).filter(self.table.c.sex == 'F').label("child_count_female"),
        )

        if not total_row:
            return (self.table.c.awc_id.label("awc_id"),) + columns

        return columns

    def _get_query_object(self, total_row=False):
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
            query = query.group_by(self.table.c.awc_id)
        return query


class MPR5ChildHealth(ChildHealthMonthlyUCR):
    """Note that this is not the same as the original.

    For the original, when children are 36 - 72 months, we only count food
    distributed for child if it was "hot", but it's possible that there is
    app logic that prevents that from ever being the case
    """
    def _column_helper(self, thr, gender_or_migrant, other=None):
        columns = self.table.c
        column = (columns.thr_eligible == 1)
        column &= {
            'rations': columns.num_rations_distributed >= 21,
            'absent': columns.num_rations_distributed.in_((0, None)),
            'partial': columns.num_rations_distributed.between(1, 20)
        }[thr]
        column &= {
            'male': columns.sex == 'M',
            'female': columns.sex == 'F',
            'migrant': columns.resident == 'no',
        }[gender_or_migrant]
        if other is None:
            return func.count(self.table.c.case_id).filter(column).label(
                "thr_rations_{}_{}".format(thr, gender_or_migrant))

        column &= {
            'st': columns.caste == 'st',
            'sc': columns.caste == 'sc',
            'others': columns.caste.notin_(('st', 'sc')),
            'disabled': columns.disabled == '1',
            'minority': columns.minority == '1',
            'male': columns.sex == 'M',
            'female': columns.sex == 'F',
        }[other]
        return func.count(self.table.c.case_id).filter(column).label(
            "thr_rations_{}_{}_{}".format(thr, gender_or_migrant, other))

    def _columns(self, total_row=False):
        columns = (
            self._column_helper("rations", "male", "st"),
            self._column_helper("rations", "female", "st"),
            self._column_helper("rations", "male", "sc"),
            self._column_helper("rations", "female", "sc"),
            self._column_helper("rations", "male", "others"),
            self._column_helper("rations", "female", "others"),
            self._column_helper("rations", "male", "disabled"),
            self._column_helper("rations", "female", "disabled"),
            self._column_helper("rations", "male", "minority"),
            self._column_helper("rations", "female", "minority"),
            self._column_helper("absent", "male"),
            self._column_helper("absent", "female"),
            self._column_helper("partial", "male"),
            self._column_helper("partial", "female"),
            self._column_helper("migrant", "male"),
            self._column_helper("migrant", "female"),
            func.count(self.table.c.case_id).filter(
                self.table.c.sex == 'M').label("child_count_male"),
            func.count(self.table.c.case_id).filter(
                self.table.c.sex == 'F').label("child_count_female"),
            func.sum(self.table.c.num_rations_distributed).filter(
                self.table.c.sex == 'M').label("thr_total_rations_male"),
            func.sum(self.table.c.num_rations_distributed).filter(
                self.table.c.sex == 'F').label("thr_total_rations_female"),
        )

        if not total_row:
            return (self.table.c.awc_id.label("awc_id"),) + columns

        return columns

    def _get_query_object(self, total_row=False):
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
            query = query.group_by(self.table.c.awc_id)
        return query
