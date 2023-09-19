from abc import ABCMeta, abstractmethod
from memoized import memoized
import re

from django.utils.functional import cached_property
from django.utils.translation import gettext

from sqlalchemy import or_
from sqlalchemy.exc import ProgrammingError

from corehq.apps.domain.models import Domain
from corehq.apps.es import GroupES, UserES
from corehq.apps.locations.models import SQLLocation
from corehq.apps.registry.exceptions import RegistryNotFound
from corehq.apps.registry.utils import RegistryPermissionCheck
from corehq.apps.reports_core.filters import Choice
from corehq.apps.userreports.exceptions import ColumnNotFoundError
from corehq.apps.userreports.reports.filters.values import SHOW_ALL_CHOICE, NONE_CHOICE
from corehq.apps.userreports.util import get_indicator_adapter
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from corehq.apps.users.util import raw_username
from corehq.util.soft_assert import soft_assert
from corehq.util.workbook_json.excel import alphanumeric_sort_key

DATA_SOURCE_COLUMN = 'data_source_column'
LOCATION = 'location'
USER = 'user'
OWNER = 'owner'
COMMCARE_PROJECT = 'commcare_project'

assert_user_passed_in = soft_assert(to="@".join(["esoergel", "dimagi.com"]), fail_if_debug=True)


class ChoiceQueryContext(object):
    """
    Context that will be passed to a choice provider function.
    """

    def __init__(self, query=None, limit=20, offset=None, page=None, user=None):
        """
        either offset or page (but not both) must be set
        page is just a helper; it is used to calculate offset as page * limit
        """
        self.query = query
        self.limit = limit
        self.user = user

        if page is not None and offset is not None:
            raise TypeError("Only one of page or offset can be passed in")
        if offset is not None:
            self.offset = offset
        elif page is not None:
            self.offset = page * limit
        else:
            raise TypeError("One of page or offset must be passed in")


class ChoiceProvider(metaclass=ABCMeta):
    location_safe = False

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

    def get_sorted_choices_for_values(self, values, user):
        return sorted(self.get_choices_for_values(values, user),
                      key=lambda choice: alphanumeric_sort_key(choice.display))

    def get_choices_for_values(self, values, user):
        choices = set(self.get_choices_for_known_values(values, user))
        if self.location_safe and not user.has_permission(self.domain, 'access_all_locations'):
            return choices

        used_values = {value for value, _ in choices}
        for value in values:
            if value not in used_values:
                choices.add(Choice(value, str(value) if value is not None else ''))
                used_values.add(value)
        return choices

    @abstractmethod
    def get_choices_for_known_values(self, values, user):
        pass


class SearchableChoice(Choice):

    def __new__(cls, value, display, searchable_text=None):
        self = super(SearchableChoice, cls).__new__(cls, value, display)
        self.searchable_text = [text for text in searchable_text or []
                                if text is not None]
        return self


class StaticChoiceProvider(ChoiceProvider):

    def __init__(self, choices):
        """
        choices must be passed in in desired sort order
        """
        self.choices = [
            choice if isinstance(choice, SearchableChoice)
            else SearchableChoice(
                choice.value, choice.display,
                searchable_text=[choice.display]
            )
            for choice in choices
        ]
        super(StaticChoiceProvider, self).__init__(None, None)

    def query(self, query_context):
        default = self.default_value(query_context.user)
        if not default:
            default = SearchableChoice(SHOW_ALL_CHOICE,
                                       "[{}]".format(gettext('Show All')), "[{}]".format(gettext('Show All')))
        filtered_set = [choice for choice in self.choices
                       if choice == default or any(query_context.query in text for text in choice.searchable_text)]
        return filtered_set[query_context.offset:query_context.offset + query_context.limit]

    def get_choices_for_known_values(self, values, user):
        return {choice for choice in self.choices
                if choice.value in values}

    def default_value(self, user):
        return None


class ChainableChoiceProvider(ChoiceProvider, metaclass=ABCMeta):
    @abstractmethod
    def query(self, query_context):
        pass

    @abstractmethod
    def get_choices_for_known_values(self, values, user):
        pass

    @abstractmethod
    def query_count(self, query_context):
        pass

    @abstractmethod
    def default_value(self, user):
        pass


class DataSourceColumnChoiceProvider(ChoiceProvider):

    def query(self, query_context):
        try:
            default = self.default_value(query_context.user)
            if not default:
                default = [Choice(SHOW_ALL_CHOICE, "[{}]".format(gettext('Show All')))]
            choices = [
                self._make_choice_from_value(value)
                for value in self.get_values_for_query(query_context)
            ]
            return default + self._deduplicate_and_sort_choices(choices)
        except ColumnNotFoundError:
            return []

    def query_count(self, query):
        # this isn't (currently) used externally, and no other choice provider relies on
        # this one's query_count, so leaving unimplemented for now
        raise NotImplementedError()

    @cached_property
    def _adapter(self):
        return get_indicator_adapter(self.report.config, load_source='choice_provider')

    @property
    def _sql_column(self):
        try:
            return self._adapter.get_table().c[self.report_filter.field]
        except KeyError as e:
            raise ColumnNotFoundError(str(e))

    def get_values_for_query(self, query_context):
        query = self._adapter.session_helper.Session.query(self._sql_column)
        if query_context.query:
            query = query.filter(self._sql_column.ilike("%{}%".format(query_context.query)))

        query = query.distinct().order_by(self._sql_column).limit(query_context.limit).offset(query_context.offset)
        try:
            values = [v[0] for v in query]
            self._adapter.track_load(len(values))
            return values
        except ProgrammingError:
            return []

    def get_choices_for_known_values(self, values, user):
        return []

    def default_value(self, user):
        return None

    def _make_choice_from_value(self, value):
        if value is None or value == '':
            return Choice(NONE_CHOICE, '[Blank]')
        return Choice(value, value)

    @staticmethod
    def _deduplicate_and_sort_choices(choices):
        return list(sorted(DataSourceColumnChoiceProvider._deduplicate_choices(choices),
                           key=lambda choice: choice.display))

    @staticmethod
    def _deduplicate_choices(choices):
        # don't return more than one result with the same value
        # this can happen e.g. for NONE_CHOICE values
        return {choice.value: choice for choice in choices}.values()


class MultiFieldDataSourceColumnChoiceProvider(DataSourceColumnChoiceProvider):

    @property
    def _sql_columns(self):
        try:
            return [self._adapter.get_table().c[field] for field in self.report_filter.fields]
        except KeyError as e:
            raise ColumnNotFoundError(str(e))

    def get_values_for_query(self, query_context):
        query = self._adapter.session_helper.Session.query(*self._sql_columns)
        if query_context.query:
            query = query.filter(
                or_(
                    *[
                        sql_column.ilike("%{}%".format(query_context.query))
                        for sql_column in self._sql_columns
                    ]
                )
            )

        query = (query.distinct().order_by(*self._sql_columns).limit(query_context.limit)
                 .offset(query_context.offset))
        try:
            result = []
            for row in query:
                for value in row:
                    self._adapter.track_load()
                    if query_context and query_context.query.lower() not in value.lower():
                        continue
                    result.append(value)
            return result
        except ProgrammingError:
            return []


class LocationChoiceProvider(ChainableChoiceProvider):

    location_safe = True

    def __init__(self, report, filter_slug):
        super(LocationChoiceProvider, self).__init__(report, filter_slug)
        self.include_descendants = False
        self.show_full_path = False
        self.location_type = None
        self.show_all_locations = False  # archived or unarchived

    def configure(self, spec):
        self.include_descendants = spec.get('include_descendants', self.include_descendants)
        self.show_full_path = spec.get('show_full_path', self.show_full_path)
        self.location_type = spec.get('location_type', self.location_type)
        self.show_all_locations = spec.get('show_all_locations', self.show_all_locations)

    def _locations_query(self, query_text, user):
        locations = SQLLocation.objects if self.show_all_locations else SQLLocation.active_objects
        if query_text:
            locations = locations.filter_by_user_input(
                domain=self.domain,
                user_input=query_text
            )

        if self.location_type:
            locations = locations.filter(location_type__code=self.location_type)

        return locations.accessible_to_user(self.domain, user).filter(domain=self.domain)

    def query(self, query_context):
        # todo: consider making this an extensions framework similar to custom expressions
        locations = self._locations_query(query_context.query, query_context.user)
        if not self.show_full_path:
            # If the full path is displayed, order by hierarchy
            locations = locations.order_by('name')

        return self._locations_to_choices(
            locations[query_context.offset:query_context.offset + query_context.limit]
        )

    def query_count(self, query, user):
        return self._locations_query(query, user).count()

    def get_choices_for_known_values(self, values, user):
        base_query = SQLLocation.objects if self.show_all_locations else SQLLocation.active_objects
        if user is not None:
            selected_locations = (base_query.filter(location_id__in=values)
                                  .accessible_to_user(self.domain, user))
        else:
            assert_user_passed_in(False, "get_choices_for_known_values was called without a user")
            selected_locations = SQLLocation.active_objects.filter(location_id__in=values)
        if self.include_descendants:
            selected_locations = SQLLocation.objects.get_queryset_descendants(
                selected_locations, include_self=True
            )

        return self._locations_to_choices(selected_locations)

    def default_value(self, user):
        """Return only the locations this user can access
        """
        location = user.get_sql_location(self.domain)
        if location:
            return self._locations_to_choices([location])

        # If the user isn't assigned to a location, they have access to all locations
        return [Choice(SHOW_ALL_CHOICE, "[{}]".format(gettext('Show All')))]

    def _locations_to_choices(self, locations):
        cached_path_display = {}

        def display(loc):
            if self.show_full_path:
                if loc.parent_id in cached_path_display:
                    path_display = '{}/{}'.format(cached_path_display[loc.parent_id], loc.name)
                else:
                    path_display = loc.get_path_display()
                cached_path_display[loc.id] = path_display
                return path_display
            else:
                return loc.display_name
        return [Choice(loc.location_id, display(loc)) for loc in locations]


class UserChoiceProvider(ChainableChoiceProvider):

    def query(self, query_context):
        user_es = get_search_users_in_domain_es_query(
            self.domain, query_context.query,
            limit=query_context.limit, offset=query_context.offset)
        return self.get_choices_from_es_query(user_es)

    def query_count(self, query, user=None):
        user_es = get_search_users_in_domain_es_query(self.domain, query, limit=0, offset=0)
        return user_es.run().total

    def get_choices_for_known_values(self, values, user):
        user_es = UserES().domain(self.domain).doc_id(values)
        return self.get_choices_from_es_query(user_es)

    @staticmethod
    def get_choices_from_es_query(user_es):
        return [Choice(user_id, raw_username(username))
                for user_id, username in user_es.values_list('_id', 'username')]

    def default_value(self, user):
        return None


class GroupChoiceProvider(ChainableChoiceProvider):

    def query(self, query_context):
        group_es = (
            GroupES().domain(self.domain).is_case_sharing()
            .search_string_query(query_context.query, default_fields=['name'])
            .size(query_context.limit).start(query_context.offset).sort('name')
        )
        return self.get_choices_from_es_query(group_es)

    def query_count(self, query, user=None):
        group_es = (
            GroupES().domain(self.domain).is_case_sharing()
            .search_string_query(query, default_fields=['name'])
        )
        return group_es.count()

    def get_choices_for_known_values(self, values, user):
        group_es = GroupES().domain(self.domain).is_case_sharing().doc_id(values)
        return self.get_choices_from_es_query(group_es)

    @staticmethod
    def get_choices_from_es_query(group_es):
        return [Choice(group_id, name)
                for group_id, name in group_es.values_list('_id', 'name', scroll=True)]

    def default_value(self, user):
        return None


class DomainChoiceProvider(ChainableChoiceProvider):

    @memoized
    def _query_domains(self, domain, query_text, user):
        domains = {domain}
        if user is None or not RegistryPermissionCheck(domain, user).can_view_registry_data(
                self.report.registry_helper.registry_slug):
            return list(domains)
        try:
            domains.update(self.report.registry_helper.visible_domains)
        except RegistryNotFound:
            return list(domains)
        if query_text:
            domains = {domain for domain in domains if re.search(query_text, domain)}
        return list(domains)

    def query(self, query_context):
        domains = self._query_domains(self.domain, query_context.query, query_context.user)
        domains.sort()
        return self._domains_to_choices(
            domains[query_context.offset:query_context.offset + query_context.limit]
        )

    def query_count(self, query, user=None):
        return len(self._query_domains(self.domain, query, user))

    def get_choices_for_known_values(self, values, user):
        domains = self._query_domains(self.domain, None, user)
        domain_options = [domain for domain in domains if domain in values]
        return self._domains_to_choices(domain_options)

    def default_value(self, user):
        return self._domains_to_choices([self.domain])

    def _domains_to_choices(self, domains):
        return [Choice(domain, Domain.get_by_name(domain).display_name()) for domain in domains]


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
        default = None
        limit = query_context.limit
        offset = query_context.offset
        query = query_context.query
        user = query_context.user
        choices = []
        if offset == 0:
            choices.append(default)
            limit -= 1
        else:
            offset -= 1

        for choice_provider in self.choice_providers:
            default = choice_provider.default_value(user)
            if limit <= 0:
                break
            query_context = ChoiceQueryContext(query=query, limit=limit, offset=offset, user=user)
            new_choices = choice_provider.query(query_context)
            choices.extend(new_choices)
            if len(new_choices):
                limit -= len(new_choices)
                offset = 0
            else:
                offset -= choice_provider.query_count(query, user=user)

        if choices[0] is None:
            if not default:
                default = [Choice(SHOW_ALL_CHOICE, "[{}]".format(gettext('Show All')))]
            choices[0] = default[0]

        return choices

    def get_choices_for_known_values(self, values, user):
        remaining_values = set(values)
        choices = []
        for choice_provider in self.choice_providers:
            if len(remaining_values) <= 0:
                break
            new_choices = choice_provider.get_choices_for_known_values(list(remaining_values), user)
            remaining_values -= {value for value, _ in new_choices}
            choices.extend(new_choices)
        return choices


class OwnerChoiceProvider(AbstractMultiProvider):
    """
    Maps ids to CommCareUser, WebUser, Group, or Location objects
    """
    choice_provider_classes = (GroupChoiceProvider, UserChoiceProvider, LocationChoiceProvider)
