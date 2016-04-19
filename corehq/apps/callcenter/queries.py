from abc import ABCMeta, abstractmethod, abstractproperty

import six
from sqlalchemy import func, distinct
from sqlalchemy.sql import operators, and_, or_, label, select

from corehq.apps.callcenter.const import *


class BaseQuery(six.with_metaclass(ABCMeta)):
    @abstractproperty
    def sql_adapter(self):
        raise NotImplementedError

    @property
    def sql_table(self):
        return self.sql_adapter.get_table()

    def _run_query(self, query):
        with self.sql_adapter.session_helper.session_context() as session:
            return list(session.execute(query))


class CaseQuery(BaseQuery):

    def __init__(self, domain, cc_case_type, owners_needing_data):
        self.owners_needing_data = owners_needing_data
        self.cc_case_type = cc_case_type
        self.domain = domain

    @abstractmethod
    def get_results(self, include_type_in_result, limit_types, start_date, end_date):
        raise NotImplementedError

    @property
    def sql_adapter(self):
        from corehq.apps.callcenter.data_source import get_report_data_sources_for_domain
        return get_report_data_sources_for_domain(self.domain).cases


class CaseQueryOpenedClosed(CaseQuery):
    """
    Count of cases where lower <= opened_on < upper
        cases_opened_{period}
        cases_opened_{case_type}_{period}

    Count of cases where lower <= closed_on < upper
        cases_closed_{period}
        cases_closed_{case_type}_{period}
    """

    def __init__(self, domain, cc_case_type, owners_needing_data, opened=True):
        self.opened = opened
        super(CaseQueryOpenedClosed, self).__init__(domain, cc_case_type, owners_needing_data)

        opened_or_closed = 'opened' if opened else 'closed'
        self.owner_column = self.sql_table.c['{}_by'.format(opened_or_closed)]
        self.date_column = self.sql_table.c['{}_on'.format(opened_or_closed)]

    def get_results(self, include_type_in_result, limit_types, start_date, end_date):
        columns = [
            label('owner_id', self.owner_column),
            label('count', func.count(self.sql_table.c.doc_id)),
        ]
        group_by = [self.owner_column]

        type_column = self.sql_table.c.type

        if include_type_in_result:
            columns.append(
                label('type', type_column)
            )
            group_by.append(type_column)

        if limit_types:
            type_filter = operators.in_op(type_column, limit_types)
        else:
            type_filter = type_column != self.cc_case_type

        query = select(
            columns
        ).where(and_(
            type_filter,
            self.date_column >= start_date,
            self.date_column < end_date,
            operators.in_op(self.owner_column, self.owners_needing_data),
        )).group_by(
            *group_by
        )

        return self._run_query(query)


class CaseQueryTotal(CaseQuery):
    """
    Count of cases where opened_on < upper and (closed == False or closed_on >= lower)

    cases_total_{period}
    cases_total_{case_type}_{period}
    """

    def get_results(self, include_type_in_result, limit_types, start_date, end_date):
        owner_column = self.sql_table.c.owner_id
        type_column = self.sql_table.c.type

        columns = [
            label('owner_id', owner_column),
            label('count', func.count(self.sql_table.c.doc_id)),
        ]
        group_by = [owner_column]
        if include_type_in_result:
            columns.append(
                label('type', type_column)
            )
            group_by.append(type_column)

        if limit_types:
            type_filter = operators.in_op(type_column, limit_types)
        else:
            type_filter = type_column != self.cc_case_type

        query = select(
            columns
        ).where(and_(
            type_filter,
            self.sql_table.c.opened_on < end_date,
            operators.in_op(owner_column, self.owners_needing_data),
            or_(
                self.sql_table.c.closed == 0,
                self.sql_table.c.closed_on >= start_date
            )
        )).group_by(
            *group_by
        )

        return self._run_query(query)


class CaseQueryActive(CaseQuery):
    """
    Count of cases where lower <= case_action.date < upper

    cases_active_{period}
    cases_active_{case_type}_{period}
    """

    @property
    def sql_adapter(self):
        from corehq.apps.callcenter.data_source import get_report_data_sources_for_domain
        return get_report_data_sources_for_domain(self.domain).case_actions

    def get_results(self, include_type_in_result, limit_types, start_date, end_date):
        owner_column = self.sql_table.c.owner_id
        type_column = self.sql_table.c.type
        columns = [
            label('owner_id', owner_column),
            label('count', func.count(distinct(self.sql_table.c.doc_id))),
        ]
        group_by = [owner_column]
        if include_type_in_result:
            columns.append(
                label('type', type_column)
            )
            group_by.append(type_column)

        if limit_types:
            type_filter = operators.in_op(type_column, limit_types)
        else:
            type_filter = type_column != self.cc_case_type

        query = select(
            columns
        ).where(and_(
            type_filter,
            self.sql_table.c.date >= start_date,
            self.sql_table.c.date < end_date,
            operators.in_op(owner_column, self.owners_needing_data),
        )).group_by(
            *group_by
        )

        return self._run_query(query)


class CaseQueryTotalLegacy(BaseQuery):
    """
    Count of cases per user that are currently open (legacy indicator).
    """
    def __init__(self, domain, cc_case_type, users_needing_data):
        self.users_needing_data = users_needing_data
        self.cc_case_type = cc_case_type
        self.domain = domain

    @property
    def sql_adapter(self):
        from corehq.apps.callcenter.data_source import get_report_data_sources_for_domain
        return get_report_data_sources_for_domain(self.domain).cases

    def get_results(self):
        query = select([
            label('user_id', self.sql_table.c.owner_id),
            label('count', func.count(self.sql_table.c.doc_id))
        ]).where(and_(
            self.sql_table.c.type != self.cc_case_type,
            self.sql_table.c.closed == 0,
            operators.in_op(self.sql_table.c.owner_id, self.users_needing_data),
        )).group_by(
            self.sql_table.c.owner_id
        )

        return self._run_query(query)


class FormQuery(BaseQuery):
    def __init__(self, domain, users_needing_data):
        self.domain = domain
        self.users_needing_data = users_needing_data

    @property
    def sql_adapter(self):
        from corehq.apps.callcenter.data_source import get_report_data_sources_for_domain
        return get_report_data_sources_for_domain(self.domain).forms


class StandardFormQuery(FormQuery):
    """
    Count of forms submitted by each user during the period (upper to lower)
    """

    def get_results(self, start_date, end_date):
        query = select([
            label('user_id', self.sql_table.c.user_id),
            label('count', func.count(self.sql_table.c.doc_id))
        ]).where(and_(
            operators.ge(self.sql_table.c.time_end, start_date),
            operators.lt(self.sql_table.c.time_end, end_date),
            operators.in_op(self.sql_table.c.user_id, self.users_needing_data)
        )).group_by(
            self.sql_table.c.user_id
        )

        return self._run_query(query)


class CustomFormQuery(FormQuery):
    """
    For specific forms add the number of forms completed during the time period (lower to upper)
    In some cases also add the average duration of the forms.
    """

    def get_results(self, xmlns, indicator_type, start_date, end_date):
        if indicator_type == TYPE_DURATION:
            aggregation = func.avg(self.sql_table.c.duration)
        else:
            aggregation = func.count(self.sql_table.c.doc_id)

        query = select([
            label('user_id', self.sql_table.c.user_id),
            label('count', aggregation)
        ]).where(and_(
            operators.ge(self.sql_table.c.time_end, start_date),
            operators.lt(self.sql_table.c.time_end, end_date),
            operators.in_op(self.sql_table.c.user_id, self.users_needing_data),
            self.sql_table.c.xmlns == xmlns,
        )).group_by(
            self.sql_table.c.user_id
        )

        return self._run_query(query)
