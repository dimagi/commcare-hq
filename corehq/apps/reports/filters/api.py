"""
API endpoints for filter options
"""
import logging

from django.views.generic import View

from braces.views import JSONResponseMixin

from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.filters.case_list import CaseListFilterUtils
from corehq.apps.users.analytics import get_search_users_in_domain_es_query
from corehq.elastic import ESError
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.logging import notify_exception

from corehq.apps.reports.filters.users import EmwfUtils, UsersUtils
from corehq.apps.es import UserES, GroupES, groups
from corehq.apps.locations.models import SQLLocation

from phonelog.models import DeviceReportEntry

logger = logging.getLogger(__name__)


class EmwfOptionsView(LoginAndDomainMixin, JSONResponseMixin, View):
    """
    Paginated options for the ExpandedMobileWorkerFilter
    """
    @property
    @memoized
    def utils(self):
        return EmwfUtils(self.domain)

    def get(self, request, domain):
        self.domain = domain
        self.q = self.request.GET.get('q', None)
        try:
            count, options = self.get_options()
            return self.render_json_response({
                'results': options,
                'total': count,
            })
        except ESError as e:
            if self.q:
                # Likely caused by an invalid user query
                # A query that causes this error immediately follows a very
                # similar query that should be caught by the else clause if it
                # errors.  If that error didn't happen, the error was probably
                # introduced by the addition of the query_string query, which
                # contains the user's input.
                logger.info('ElasticSearch error caused by query "%s": %s',
                            self.q, e)
            else:
                # The error was our fault
                notify_exception(request, e)
        return self.render_json_response({
            'results': [],
            'total': 0,
        })

    def get_locations_query(self, query):
        return SQLLocation.active_objects.filter_path_by_user_input(self.domain, query)

    def get_locations(self, query, start, size):
        """
        start: The index of the first item to be returned
        size: The number of items to return
        """
        return map(self.utils.location_tuple,
                   self.get_locations_query(query)[start:start + size])

    def get_locations_size(self, query):
        return self.get_locations_query(query).count()

    @property
    def data_sources(self):
        return [
            (self.get_static_options_size, self.get_static_options),
            (self.get_groups_size, self.get_groups),
            (self.get_locations_size, self.get_locations),
            (self.get_users_size, self.get_users),
        ]

    def get_options(self):
        page = int(self.request.GET.get('page', 1))
        size = int(self.request.GET.get('page_limit', 10))
        start = size * (page - 1)
        count, options = paginate_options(self.data_sources, self.q, start, size)
        return count, [{'id': id_, 'text': text} for id_, text in options]

    def get_static_options_size(self, query):
        return len(self.get_all_static_options(query))

    def get_all_static_options(self, query):
        return [user_type for user_type in self.utils.static_options
                if query.lower() in user_type[1].lower()]

    def get_static_options(self, query, start, size):
        return self.get_all_static_options(query)[start:start+size]

    def get_es_query_strings(self, query):
        if query and query.strip():
            tokens = query.split()
            return ['%s*' % tokens.pop()] + tokens

    def user_es_query(self, query):
        search_fields = ["first_name", "last_name", "base_username"]
        return (UserES()
                .domain(self.domain)
                .search_string_query(query, default_fields=search_fields))

    def get_users_size(self, query):
        return self.user_es_query(query).count()

    def get_users(self, query, start, size):
        users = (self.user_es_query(query)
                 .fields(['_id', 'username', 'first_name', 'last_name', 'doc_type'])
                 .start(start)
                 .size(size)
                 .sort("username.exact"))
        return [self.utils.user_tuple(u) for u in users.run().hits]

    def get_groups_size(self, query):
        return self.group_es_query(query).count()

    def group_es_query(self, query, group_type="reporting"):
        if group_type == "reporting":
            type_filter = groups.is_reporting()
        elif group_type == "case_sharing":
            type_filter = groups.is_case_sharing()
        else:
            raise TypeError("group_type '{}' not recognized".format(group_type))

        return (GroupES()
                .domain(self.domain)
                .filter(type_filter)
                .not_deleted()
                .search_string_query(query, default_fields=["name"]))

    def get_groups(self, query, start, size):
        groups = (self.group_es_query(query)
                  .fields(['_id', 'name'])
                  .start(start)
                  .size(size)
                  .sort("name.exact"))
        return [self.utils.reporting_group_tuple(g) for g in groups.run().hits]


class LocationRestrictedEmwfOptionsMixin(object):
    def extra_data_sources(self):
        # extra data sources to be included for filtering
        raise NotImplementedError('Not implemented yet')

    def get_locations_query(self, query):
        return (SQLLocation.active_objects
                .filter_path_by_user_input(self.domain, query)
                .accessible_to_user(self.request.domain, self.request.couch_user))

    def get_users(self, query, start, size):
        """
        :return: tuples for accessible users filtered with query
        """
        users = (self.user_es_query(query)
                 .fields(['_id', 'username', 'first_name', 'last_name', 'doc_type'])
                 .start(start)
                 .size(size)
                 .sort("username.exact"))
        if not self.request.can_access_all_locations:
            accessible_location_ids = SQLLocation.active_objects.accessible_location_ids(self.request.domain,
                                                                                         self.request.couch_user)
            users = users.location(accessible_location_ids)
        return [self.utils.user_tuple(u) for u in users.run().hits]

    @property
    def data_sources(self):
        # data sources for options for selection in filter
        sources = []
        if self.request.can_access_all_locations:
            sources.append((self.get_static_options_size, self.get_static_options))
            sources.append((self.get_groups_size, self.get_groups))
            sources.extend(self.extra_data_sources())

        sources.append((self.get_locations_size, self.get_locations))
        # appending this in the end to avoid long list of users delaying
        # locations, groups etc in the list on pagination
        sources.append((self.get_users_size, self.get_users))
        return sources


class MobileWorkersOptionsView(EmwfOptionsView):
    """
    Paginated Options for the Mobile Workers selection tool
    """
    urlname = 'users_select2_options'

    @property
    @memoized
    def utils(self):
        return UsersUtils(self.domain)

    @property
    def data_sources(self):
        return [
            (self.get_users_size, self.get_users),
        ]

    def user_es_query(self, query):
        query = super(MobileWorkersOptionsView, self).user_es_query(query)
        return query.mobile_users()


@location_safe
class LocationRestrictedEmwfOptions(LocationRestrictedEmwfOptionsMixin, EmwfOptionsView):
    def extra_data_sources(self):
        return []


@location_safe
class CaseListFilterOptions(LocationRestrictedEmwfOptionsMixin, EmwfOptionsView):

    @property
    @memoized
    def utils(self):
        return CaseListFilterUtils(self.domain)

    def extra_data_sources(self):
        return [(self.get_sharing_groups_size, self.get_sharing_groups)]

    def get_sharing_groups_size(self, query):
        return self.group_es_query(query, group_type="case_sharing").count()

    def get_sharing_groups(self, query, start, size):
        groups = (self.group_es_query(query, group_type="case_sharing")
                  .fields(['_id', 'name'])
                  .start(start)
                  .size(size)
                  .sort("name.exact"))
        return map(self.utils.sharing_group_tuple, groups.run().hits)


def paginate_options(data_sources, query, start, size):
    """
    Returns the appropriate slice of values from the data sources
    data_sources is a list of (count_fn, getter_fn) tuples
        count_fn returns the total number of entries in a data source,
        getter_fn takes in a start and size parameter and returns entries
    """
    # Note this is pretty confusing, check TestEmwfPagination for reference
    options = []
    total = 0
    for get_size, get_objects in data_sources:
        count = get_size(query)
        total += count

        if start > count:  # skip over this whole data source
            start -= count
            continue

        # return a page of objects
        objects = list(get_objects(query, start, size))
        start = 0
        size -= len(objects)  # how many more do we need for this page?
        options.extend(objects)
    return total, options


class DeviceLogFilter(LoginAndDomainMixin, JSONResponseMixin, View):
    field = None

    def get(self, request, domain):
        q = self.request.GET.get('q', None)
        field_filter = {self.field + "__startswith": q}
        query_set = (
            DeviceReportEntry.objects
            .filter(domain=domain)
            .filter(**field_filter)
            .distinct(self.field)
            .values_list(self.field, flat=True)
            .order_by(self.field)
        )
        values = query_set[self._offset():self._offset() + self._page_limit() + 1]
        return self.render_json_response({
            'results': [{'id': v, 'text': v} for v in values[:self._page_limit()]],
            'more': len(values) > self._page_limit(),
        })

    def _page_limit(self):
        page_limit = self.request.GET.get("page_limit", 10)
        try:
            return int(page_limit)
        except ValueError:
            return 10

    def _page(self):
        page = self.request.GET.get("page", 1)
        try:
            return int(page)
        except ValueError:
            return 1

    def _offset(self):
        return self._page_limit() * (self._page() - 1)


class DeviceLogUsers(DeviceLogFilter):

    def get(self, request, domain):
        q = self.request.GET.get('q', None)
        users_query = (get_search_users_in_domain_es_query(domain, q, self._page_limit(), self._offset())
            .show_inactive()
            .remove_default_filter("not_deleted")
            .source("username")
        )
        values = [x['username'].split("@")[0] for x in users_query.run().hits]
        count = users_query.count()
        return self.render_json_response({
            'results': [{'id': v, 'text': v} for v in values],
            'total': count,
        })


class DeviceLogIds(DeviceLogFilter):
    field = 'device_id'
