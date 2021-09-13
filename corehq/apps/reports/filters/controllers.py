from memoized import memoized

from corehq.apps.es import GroupES, UserES, groups
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.const import DEFAULT_PAGE_LIMIT
from corehq.apps.reports.extension_points import customize_user_query
from corehq.apps.reports.filters.case_list import CaseListFilterUtils
from corehq.apps.reports.filters.users import EmwfUtils, UsersUtils
from corehq.apps.reports.util import SimplifiedUserInfo


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


class EmwfOptionsController(object):
    namespace_locations = True
    case_sharing_only = False

    def __init__(self, request, domain, search, case_sharing_only=False):
        self.request = request
        self.domain = domain
        self.search = search
        self.case_sharing_only = case_sharing_only

    @property
    @memoized
    def utils(self):
        return EmwfUtils(self.domain, namespace_locations=self.namespace_locations)

    def get_all_static_options(self, query):
        return [user_type for user_type in self.utils.static_options
                if query.lower() in user_type[1].lower()]

    def get_static_options_size(self, query):
        return len(self.get_all_static_options(query))

    def get_static_options(self, query, start, size):
        return self.get_all_static_options(query)[start:start + size]

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

    def get_groups_size(self, query):
        return self.group_es_query(query).count()

    def get_groups(self, query, start, size):
        groups_query = (self.group_es_query(query)
                        .fields(['_id', 'name'])
                        .start(start)
                        .size(size)
                        .sort("name.exact"))
        return [self.utils.reporting_group_tuple(g) for g in groups_query.run().hits]

    def get_locations_query(self, query):
        show_inactive = self.request.GET.get('show_inactive') == 'true'
        show_all = self.request.GET.get('show_all') == 'true'

        locations = SQLLocation.objects.filter_by_user_input(self.domain, query)
        if not show_all:
            locations = locations.filter(is_archived=show_inactive)

        if self.case_sharing_only:
            locations = locations.filter(location_type__shares_cases=True)
        return locations.accessible_to_user(self.domain, self.request.couch_user)

    def get_locations_size(self, query):
        return self.get_locations_query(query).count()

    def get_locations(self, query, start, size):
        """
        start: The index of the first item to be returned
        size: The number of items to return
        """
        return list(map(self.utils.location_tuple,
                        self.get_locations_query(query)[start:start + size]))

    def _get_users(self, query, start, size, include_inactive=False):
        if include_inactive:
            user_query = self.all_user_es_query(query)
        else:
            user_query = self.active_user_es_query(query)
        users = (user_query
                 .fields(SimplifiedUserInfo.ES_FIELDS)
                 .start(start)
                 .size(size)
                 .sort("username.exact"))
        if not self.request.can_access_all_locations:
            accessible_location_ids = SQLLocation.active_objects.accessible_location_ids(
                self.request.domain, self.request.couch_user)
            users = users.location(accessible_location_ids)
        users = customize_user_query(self.request.couch_user, self.domain, users)
        return [self.utils.user_tuple(u) for u in users.run().hits]

    def active_user_es_query(self, query):
        search_fields = ["first_name", "last_name", "base_username"]
        return (UserES()
                .domain(self.domain)
                .search_string_query(query, default_fields=search_fields))

    def all_user_es_query(self, query):
        return self.active_user_es_query(query).show_inactive()

    def get_all_users_size(self, query):
        return self.all_user_es_query(query).count()

    def get_active_users_size(self, query):
        return self.active_user_es_query(query).count()

    def get_all_users(self, query, start, size):
        return self._get_users(query, start, size, include_inactive=True)

    def get_active_users(self, query, start, size):
        return self._get_users(query, start, size, include_inactive=False)

    @property
    def data_sources(self):
        if self.request.can_access_all_locations:
            return [
                (self.get_static_options_size, self.get_static_options),
                (self.get_groups_size, self.get_groups),
                (self.get_locations_size, self.get_locations),
                (self.get_all_users_size, self.get_all_users),
            ]
        else:
            return [
                (self.get_locations_size, self.get_locations),
                (self.get_all_users_size, self.get_all_users),
            ]

    @property
    @memoized
    def page(self):
        if self.request.method == 'POST':
            return int(self.request.POST.get('page', 1))
        return int(self.request.GET.get('page', 1))

    @property
    @memoized
    def size(self):
        if self.request.method == 'POST':
            return int(self.request.POST.get('page_limit', DEFAULT_PAGE_LIMIT))
        return int(self.request.GET.get('page_limit', DEFAULT_PAGE_LIMIT))

    def get_options(self, show_more=False):
        """
        If `show_more` = True, then the result returns a tuple where the first
        value is a boolean of whether more additional pages are still available
        (used by Select 2). Otherwise the first value in the tuple returned
        is the total.
        :param show_more: (optional)
        :return: (int) count or (bool) has_more, (list) results
        """
        start = self.size * (self.page - 1)
        count, options = paginate_options(
            self.data_sources,
            self.search,
            start,
            self.size
        )
        results = [
            {'id': entry[0], 'text': entry[1]} if len(entry) == 2 else
            {'id': entry[0], 'text': entry[1], 'is_active': entry[2]} for entry
            in options
        ]

        if show_more:
            has_more = (self.page * self.size) < count
            return has_more, results
        return count, results


class MobileWorkersOptionsController(EmwfOptionsController):

    @property
    @memoized
    def utils(self):
        return UsersUtils(self.domain)

    def get_post_options(self):
        page = int(self.request.POST.get('page', 1))
        size = int(self.request.POST.get('page_limit', DEFAULT_PAGE_LIMIT))
        start = size * (page - 1)
        count, options = paginate_options(
            self.data_sources,
            self.search,
            start,
            size
        )
        return count, [{'id': id_, 'text': text} for id_, text in options]

    @property
    def data_sources(self):
        return [
            (self.get_active_users_size, self.get_active_users),
        ]

    def active_user_es_query(self, query):
        query = super(MobileWorkersOptionsController, self).active_user_es_query(query)
        return query.mobile_users()


class CaseListFilterOptionsController(EmwfOptionsController):

    def get_sharing_groups(self, query, start, size):
        groups = (self.group_es_query(query, group_type="case_sharing")
                  .fields(['_id', 'name'])
                  .start(start)
                  .size(size)
                  .sort("name.exact"))
        return list(map(self.utils.sharing_group_tuple, groups.run().hits))

    @property
    @memoized
    def utils(self):
        return CaseListFilterUtils(self.domain)

    @property
    # Case list shows all users, instead of just active users
    def data_sources(self):
        if self.request.can_access_all_locations:
            return [
                (self.get_static_options_size, self.get_static_options),
                (self.get_groups_size, self.get_groups),
                (self.get_sharing_groups_size, self.get_sharing_groups),
                (self.get_locations_size, self.get_locations),
                (self.get_all_users_size, self.get_all_users),
            ]
        else:
            return [
                (self.get_locations_size, self.get_locations),
                (self.get_active_users_size, self.get_active_users),
            ]

    def get_sharing_groups_size(self, query):
        return self.group_es_query(query, group_type="case_sharing").count()


class ReassignCaseOptionsController(CaseListFilterOptionsController):

    @property
    def data_sources(self):
        """
        Includes case-sharing groups but not reporting groups
        """
        sources = []
        if self.request.can_access_all_locations:
            sources.append((self.get_sharing_groups_size, self.get_sharing_groups))
        sources.append((self.get_locations_size, self.get_locations))
        sources.append((self.get_active_users_size, self.get_active_users))
        return sources


class LocationGroupOptionsController(EmwfOptionsController):

    @property
    def data_sources(self):
        return [
            (self.get_groups_size, self.get_groups),
            (self.get_locations_size, self.get_locations),
        ]
