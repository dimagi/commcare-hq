from abc import ABCMeta, abstractmethod

from sqlalchemy.exc import ProgrammingError
from corehq.apps.es import GroupES, UserES
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.exceptions import ColumnNotFoundError
from corehq.apps.userreports.sql import IndicatorSqlAdapter
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from corehq.apps.users.util import raw_username

DATA_SOURCE_COLUMN = 'data_source_column'
LOCATION = 'location'
USER = 'user'
OWNER = 'owner'


class ChoiceQueryContext(object):
    """
    Context that will be passed to a choice provider function.
    """
    def __init__(self, query=None, limit=20, offset=None, page=None):
        """
        either offset or page (but not both) must be set
        page is just a helper; it is used to calculate offset as page * limit
        """
        self.query = query
        self.limit = limit

        if page is not None and offset is not None:
            raise TypeError("Only one of page or offset can be passed in")
        if offset is not None:
            self.offset = offset
        elif page is not None:
            self.offset = page * limit
        else:
            raise TypeError("One of page or offset must be passed in")


class ChoiceProvider(object):
    __metaclass__ = ABCMeta

    def __init__(self, report, filter_slug):
        self.report = report
        self.filter_slug = filter_slug

    def configure(self, spec):
        """
        Custom configuration for the choice provider can live here
        """
        pass

    @property
    def report_filter(self):
        return self.report.get_ui_filter(self.filter_slug)

    @property
    def domain(self):
        return self.report.domain

    @abstractmethod
    def query(self, query_context):
        pass

    def get_sorted_choices_for_values(self, values):
        return sorted(self.get_choices_for_values(values), key=lambda choice: choice.display)

    def get_choices_for_values(self, values):
        choices = set(self.get_choices_for_known_values(values))
        used_values = {value for value, _ in choices}
        for value in values:
            if value not in used_values:
                choices.add(Choice(value, unicode(value) if value is not None else ''))
                used_values.add(value)
        return choices

    @abstractmethod
    def get_choices_for_known_values(self, values):
        pass


class ChainableChoiceProvider(ChoiceProvider):
    __metaclass__ = ABCMeta

    @abstractmethod
    def query(self, query_context):
        pass

    @abstractmethod
    def get_choices_for_known_values(self, values):
        pass

    @abstractmethod
    def query_count(self, query_context):
        pass


class DataSourceColumnChoiceProvider(ChoiceProvider):

    def query(self, query_context):
        try:
            return [Choice(value, value)
                    for value in self.get_values_for_query(query_context)]
        except ColumnNotFoundError:
            return []

    def query_count(self, query):
        # this isn't (currently) used externally, and no other choice provider relies on
        # this one's query_count, so leaving unimplemented for now
        raise NotImplementedError()

    @property
    def _adapter(self):
        return IndicatorSqlAdapter(self.report.config)

    @property
    def _sql_column(self):
        try:
            return self._adapter.get_table().c[self.report_filter.field]
        except KeyError as e:
            raise ColumnNotFoundError(e.message)

    def get_values_for_query(self, query_context):
        query = self._adapter.session_helper.Session.query(self._sql_column)
        if query_context.query:
            query = query.filter(self._sql_column.ilike(u"%{}%".format(query_context.query)))

        query = query.distinct().order_by(self._sql_column).limit(query_context.limit).offset(query_context.offset)
        try:
            return [v[0] for v in query]
        except ProgrammingError:
            return []

    def get_choices_for_known_values(self, values):
        return []


class LocationChoiceProvider(ChainableChoiceProvider):

    def __init__(self, report, filter_slug):
        super(LocationChoiceProvider, self).__init__(report, filter_slug)
        self.include_descendants = False

    def configure(self, spec):
        self.include_descendants = spec.get('include_descendants', self.include_descendants)

    def _locations_query(self, query_text):
        if query_text:
            return SQLLocation.active_objects.filter_path_by_user_input(
                domain=self.domain, user_input=query_text)
        else:
            return SQLLocation.active_objects.filter(domain=self.domain)

    def query(self, query_context):
        # todo: consider making this an extensions framework similar to custom expressions
        # todo: does this need fancier permission restrictions and what not?
        # see e.g. locations.views.child_locations_for_select2

        locations = self._locations_query(query_context.query).order_by('name')

        return [
            Choice(loc.location_id, loc.display_name) for loc in
            locations[query_context.offset:query_context.offset + query_context.limit]
        ]

    def query_count(self, query):
        return self._locations_query(query).count()

    def get_choices_for_known_values(self, values):
        selected_locations = SQLLocation.active_objects.filter(location_id__in=values)
        if self.include_descendants:
            selected_locations = SQLLocation.get_queryset_descendants(selected_locations, include_self=True)

        return [Choice(loc.location_id, loc.display_name) for loc in selected_locations]


class UserChoiceProvider(ChainableChoiceProvider):
    def query(self, query_context):
        user_es = get_search_users_in_domain_es_query(
            self.domain, query_context.query,
            limit=query_context.limit, offset=query_context.offset)
        return self.get_choices_from_es_query(user_es)

    def query_count(self, query):
        user_es = get_search_users_in_domain_es_query(self.domain, query, limit=0, offset=0)
        return user_es.run().total

    def get_choices_for_known_values(self, values):
        user_es = UserES().domain(self.domain).doc_id(values)
        return self.get_choices_from_es_query(user_es)

    @staticmethod
    def get_choices_from_es_query(user_es):
        return [Choice(user_id, raw_username(username))
                for user_id, username in user_es.values_list('_id', 'username')]


class GroupChoiceProvider(ChainableChoiceProvider):
    def query(self, query_context):
        group_es = (
            GroupES().domain(self.domain).is_case_sharing()
            .search_string_query(query_context.query, default_fields=['name'])
            .size(query_context.limit).start(query_context.offset).sort('name')
        )
        return self.get_choices_from_es_query(group_es)

    def query_count(self, query):
        group_es = (
            GroupES().domain(self.domain).is_case_sharing()
            .search_string_query(query, default_fields=['name'])
        )
        return group_es.size(0).run().total

    def get_choices_for_known_values(self, values):
        group_es = GroupES().domain(self.domain).is_case_sharing().doc_id(values)
        return self.get_choices_from_es_query(group_es)

    @staticmethod
    def get_choices_from_es_query(group_es):
        return [Choice(group_id, name)
                for group_id, name in group_es.values_list('_id', 'name')]


class AbstractMultiProvider(ChoiceProvider):

    choice_provider_classes = ()

    def __init__(self, report, filter_slug):
        super(AbstractMultiProvider, self).__init__(report, filter_slug)

        self.choice_providers = [
            klass(report, filter_slug) for klass in self.choice_provider_classes]
        bad_choice_providers = [
            choice_provider for choice_provider in self.choice_providers
            if not isinstance(choice_provider, ChainableChoiceProvider)]
        assert not bad_choice_providers, bad_choice_providers

    def query(self, query_context):
        limit = query_context.limit
        offset = query_context.offset
        query = query_context.query
        choices = []
        for choice_provider in self.choice_providers:
            if limit <= 0:
                break
            query_context = ChoiceQueryContext(query=query, limit=limit, offset=offset)
            new_choices = choice_provider.query(query_context)
            choices.extend(new_choices)
            if len(new_choices):
                limit -= len(new_choices)
                offset = 0
            else:
                offset -= choice_provider.query_count(query)
        return choices

    def get_choices_for_known_values(self, values):
        remaining_values = set(values)
        choices = []
        for choice_provider in self.choice_providers:
            if len(remaining_values) <= 0:
                break
            new_choices = choice_provider.get_choices_for_known_values(list(remaining_values))
            remaining_values -= {value for value, _ in new_choices}
            choices.extend(new_choices)
        return choices


class OwnerChoiceProvider(AbstractMultiProvider):
    """
    Maps ids to CommCareUser, WebUser, Group, or Location objects
    """
    choice_provider_classes = (GroupChoiceProvider, UserChoiceProvider, LocationChoiceProvider)
