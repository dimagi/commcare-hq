from __future__ import absolute_import
from __future__ import unicode_literals

from collections import OrderedDict

import six
import sqlagg
import sqlalchemy
from sqlalchemy import select
from sqlalchemy.sql import func

from corehq.sql_db.connections import connection_manager
from corehq.apps.userreports.custom.data_source import ConfigurableReportCustomQueryProvider


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

    def _get_query_object(self, total_row=False):
        raise NotImplementedError()

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
            (r.owner_id, r._asdict())
            for r in query_obj.all()
        ])

    def get_total_row(self):
        query_obj = self._get_query_object(total_row=True)
        return ["Total"] + [r or 0 for r in query_obj.first()]

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
            columns = (self.table.c.awc_id.label("owner_id"),) + columns
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
            func.count(self.table.c.case_id).filter(self.table.c.sex == 'F').label("child_count_female"),
            func.count(self.table.c.case_id).filter(self.table.c.sex == 'M').label("child_count_male"),
            self._column_helper("partial", "female"),
            self._column_helper("partial", "male"),
        )

        if not total_row:
            return (self.table.c.awc_id.label("owner_id"),) + columns

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
            "thr_rations_{}_{}".format(gender_or_migrant, other))

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
            self._column_helper("rations", "migrant", "male"),
            self._column_helper("rations", "migrant", "female"),
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
            return (self.table.c.awc_id.label("owner_id"),) + columns

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


class TwoStageAggregateCustomQueryProvider(ConfigurableReportCustomQueryProvider):
    """
    Reasons this is needed:
      - Filter column based on a SQL aggregate / case function

    This is a completely generic class that should work with any UCR report that needs to do
    filters based off an aggregate query (e.g. a sum_when column).

    Any column listed in AGGREGATE_FILTERS will be filtered in an outer query with the main
    query running in a subquery first.
    """
    # these filters will be applied in the outer query
    AGGREGATE_FILTERS = []

    def __init__(self, report_data_source):
        self.report_data_source = report_data_source
        self.helper = self.report_data_source.helper
        self.table = self.helper.get_table()

    def _split_filters(self, filters):
        """
        Returns a data structure of filters split for the inner query and the outer query
        based on self.AGGREGATE_FILTERS
        :param filters: The complete list of filters
        :param filter_values: The complete list of filter_values
        :return: {
           "inner": [ list of inner filters ],
           "outer": [ list of outer filters ],
        }
        """
        # specifying ancestor_location returns an ANDFilter and does not have a column name
        # assume that it should go into inner filters
        complex_filters = [f for f in filters if not hasattr(f, 'column_name')]
        simple_filters = [f for f in filters if hasattr(f, 'column_name')]
        inner_filters = [f for f in simple_filters if f.column_name not in self.AGGREGATE_FILTERS]
        outer_filters = [f for f in simple_filters if f.column_name in self.AGGREGATE_FILTERS]
        return {
            'inner': inner_filters + complex_filters,
            'outer': outer_filters,
        }

    def _get_select_query(self):
        # break filters into those that can be used in the inner query and those that
        # need to bubble up to the outer query (aggregates)
        split_filters = self._split_filters(self.helper._filters)
        # a lot of what follows is copy/modified from SqlData._get_data() and corresponding call chain
        # e.g. SimpleQueryMeta._build_query_generic in sqlagg
        query_context = sqlagg.QueryContext(
            self.table.name,
            filters=split_filters['inner'],
            group_by=self.report_data_source.group_by,
            # note: is this necessary to add?
            # order_by=self.order_by,
        )
        for c in self.report_data_source.columns:
            query_context.append_column(c.view)

        if len(query_context.query_meta.values()) > 1:
            raise Exception('Use of this class assumes only one query meta value!')

        query_meta = list(query_context.query_meta.values())[0]
        # note: sqlagg doesn't expose access to sqlalchemy except through this private method
        query = query_meta._build_query()
        if split_filters['outer']:
            # if there are outer filters we have to do a two-stage query
            # first add a subquery (with alias)
            query = query.alias().select()
            for f in split_filters['outer']:
                # then apply outer filters to the subquery
                query.append_whereclause(f.build_expression())

        return query

    def get_data(self, start=None, limit=None):
        select_query = self._get_select_query()
        if start is not None:
            select_query = select_query.offset(start)
        if limit is not None:
            select_query = select_query.limit(limit)

        with self.helper.session_helper().session_context() as session:
            results = session.connection().execute(
                select_query,
                **self.helper.sql_alchemy_filter_values
            ).fetchall()

        def _extract_aggregate_key(row):
            return tuple(getattr(row, key_component) for key_component in self.report_data_source.group_by)

        def _row_proxy_to_dict(row):
            return dict(row.items())  # noqa: RowProxy doesn't support iteritems

        return OrderedDict([
            (_extract_aggregate_key(row), _row_proxy_to_dict(row)) for row in results
        ])

    def get_total_row(self):
        raise NotImplementedError("This data source doesn't support total rows")

    def get_total_records(self):
        select_query = self._get_select_query()
        with self.helper.session_helper().session_context() as session:
            count_query = select([func.count()]).select_from(select_query.alias())
            return session.connection().execute(count_query, **self.helper.sql_alchemy_filter_values).scalar()


CcsRecordMonthlyViewAlchemy = sqlalchemy.Table(
    'ccs_record_monthly_view', metadata, autoload=True
)


class CcsRecordMonthlyUCR(ConfigurableReportCustomQueryProvider):
    def __init__(self, report_data_source):
        self.report_data_source = report_data_source
        self.helper = self.report_data_source.helper
        self.helper.set_table(CcsRecordMonthlyViewAlchemy)

    @property
    def table(self):
        return CcsRecordMonthlyViewAlchemy

    def _get_query_object(self, total_row=False):

        def format_column(title, logic):
            return func.count(self.table.c.case_id).filter(logic).label(title)

        pregnant = self.table.c.pregnant == 1
        lactating = self.table.c.lactating == 1
        st_caste = self.table.c.caste == 'st'
        sc_caste = self.table.c.caste == 'sc'
        rations_gte_21 = self.table.c.num_rations_distributed >= 21
        rations_lt_21 = (0 < self.table.c.num_rations_distributed) & (self.table.c.num_rations_distributed < 21)
        disabled = self.table.c.disabled == 'yes'
        minority = self.table.c.minority == 'yes'
        rations_none = (self.table.c.num_rations_distributed == 0) |\
                       (self.table.c.num_rations_distributed.is_(None))
        migrant = self.table.c.resident == 'no'
        columns = (
            format_column(title='thr_rations_pregnant_st', logic=(pregnant & st_caste & rations_gte_21)),
            format_column(title='thr_rations_lactating_st', logic=(lactating & st_caste & rations_gte_21)),
            format_column(title='thr_rations_pregnant_sc', logic=(pregnant & sc_caste & rations_gte_21)),
            format_column(title='thr_rations_lactating_sc', logic=(lactating & sc_caste & rations_gte_21)),
            format_column(title='thr_rations_pregnant_others', logic=(pregnant & (not sc_caste) &
                                                                      (not st_caste) & rations_gte_21)),
            format_column(title='thr_rations_lactating_others', logic=(lactating & (not sc_caste) &
                                                                       (not st_caste) & rations_gte_21)),
            format_column(title='thr_rations_pregnant_disabled', logic=(pregnant & disabled & rations_gte_21)),
            format_column(title='thr_rations_lactating_disabled', logic=(lactating & disabled & rations_gte_21)),
            format_column(title='thr_rations_pregnant_minority', logic=(pregnant & minority & rations_gte_21)),
            format_column(title='thr_rations_lactating_minority', logic=(lactating & minority & rations_gte_21)),
            format_column(title='thr_rations_absent_pregnant', logic=(pregnant & rations_none)),
            format_column(title='thr_rations_absent_lactating', logic=(lactating & rations_none)),
            format_column(title='thr_rations_partial_pregnant', logic=(pregnant & rations_lt_21)),
            format_column(title='thr_rations_partial_lactating', logic=(lactating & rations_lt_21)),
            format_column(title='thr_rations_migrant_pregnant', logic=(pregnant & rations_gte_21 & migrant)),
            format_column(title='thr_rations_migrant_lactating', logic=(lactating & rations_gte_21 & migrant)),
            format_column(title='pregnant', logic=pregnant),
            format_column(title='lactating', logic=lactating),
            format_column(title='thr_total_rations_pregnant', logic=(pregnant & rations_gte_21)),
            format_column(title='thr_total_rations_lactating', logic=(lactating & rations_gte_21)),
        )

        if not total_row:
            columns = (self.table.c.awc_id.label("owner_id"),) + columns

        filters = self.helper.sql_alchemy_filters
        filter_values = self.helper.sql_alchemy_filter_values

        query = (
            self.helper.adapter.session_helper.Session.query(
                *columns
            )
            .filter(*filters)
            .params(filter_values)
        )
        if not total_row:
            query = query.group_by(self.table.c.awc_id)
        return query

    def get_data(self, start=None, limit=None):
        query_obj = self._get_query_object()
        if start:
            query_obj = query_obj.start(start)
        if limit:
            query_obj = query_obj.limit(limit)
        return OrderedDict([
            (r.owner_id, r._asdict())
            for r in query_obj.all()
        ])

    def get_total_row(self):
        query_obj = self._get_query_object(total_row=True)
        return ["Total"] + [r or 0 for r in query_obj.first()]

    def get_total_records(self):
        return self._get_query_object().count()


class MPR2BIPregDeliveryDeathList(TwoStageAggregateCustomQueryProvider):
    AGGREGATE_FILTERS = ['dead_preg_count']
