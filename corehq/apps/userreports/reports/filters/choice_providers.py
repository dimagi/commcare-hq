from abc import ABCMeta, abstractmethod
from sqlalchemy.exc import ProgrammingError
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.users.analytics import get_search_users_in_domain_es_query, \
    get_bulk_get_users_by_id_es_query
from corehq.apps.users.util import raw_username


DATA_SOURCE_COLUMN = 'data_source_column'
LOCATION = 'location'
USER = 'user'


class ChoiceQueryContext(object):
    """
    Context that will be passed to a choice provider function.
    """
    def __init__(self, query=None, limit=20, page=0):
        self.query = query
        self.limit = limit
        self.page = page

    @property
    def offset(self):
        return self.page * self.limit


class ChoiceProvider(object):
    __metaclass__ = ABCMeta

    def __init__(self, report, filter_slug):
        self.report = report
        self.filter_slug = filter_slug

    @property
    def report_filter(self):
        return self.report.get_ui_filter(self.filter_slug)

    @property
    def domain(self):
        return self.report.domain

    @abstractmethod
    def query(self, query_context):
        pass

    @abstractmethod
    def get_choices_for_values(self, values):
        pass


class DataSourceColumnChoiceProvider(ChoiceProvider):

    def query(self, query_context):
        return self.get_choices_for_values(self.get_values_for_query(query_context))

    @property
    def _adapter(self):
        return IndicatorSqlAdapter(self.report.config)

    @property
    def _sql_column(self):
        return self._adapter.get_table().c[self.report_filter.field]

    def get_values_for_query(self, query_context):
        query = self._adapter.session_helper.Session.query(self._sql_column)
        if query_context.query:
            query = query.filter(self._sql_column.contains(query_context.query))

        query = query.distinct().order_by(self._sql_column).limit(query_context.limit).offset(query_context.offset)
        try:
            return [v[0] for v in query]
        except ProgrammingError:
            return []

    def get_choices_for_values(self, values):
        return [Choice(value, value) for value in values]


class LocationChoiceProvider(ChoiceProvider):

    def query(self, query_context):
        # todo: consider making this an extensions framework similar to custom expressions
        # todo: does this need fancier permission restrictions and what not?
        # see e.g. locations.views.child_locations_for_select2
        if query_context.query:
            locations = SQLLocation.active_objects.filter_path_by_user_input(
                domain=self.domain, user_input=query_context.query
            )
        else:
            locations = SQLLocation.active_objects.filter(domain=self.domain)
        return [
            Choice(loc.location_id, loc.display_name) for loc in
            locations[query_context.offset:query_context.offset + query_context.limit]
        ]

    def get_choices_for_values(self, values):
        display_name_by_id = dict(
            SQLLocation.active_objects.filter(location_id__in=values)
            .values_list('location_id', 'display_name'))
        return [Choice(value, display_name_by_id.get(value, value)) for value in values]


class UserChoiceProvider(ChoiceProvider):
    def query(self, query_context):
        user_es = get_search_users_in_domain_es_query(
            self.domain, query_context.query,
            limit=query_context.limit, page=query_context.page)
        return self.get_choices_from_es_query(user_es)

    def get_choices_for_values(self, values):
        user_es = get_bulk_get_users_by_id_es_query(self.domain, values)
        choices = self.get_choices_from_es_query(user_es)
        used_values = {value for value, _ in choices}
        for value in values:
            if value not in used_values:
                choices.append(Choice(value, value))
                used_values.add(value)
        return choices

    @staticmethod
    def get_choices_from_es_query(user_es):
        return [Choice(user_id, raw_username(username))
                for user_id, username in user_es.values_list('_id', 'username')]
