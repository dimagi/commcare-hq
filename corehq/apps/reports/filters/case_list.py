from django.utils.translation import ugettext as _

from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import LocationType, SQLLocation

from .users import ExpandedMobileWorkerFilter, EmwfUtils
from .api import EmwfOptionsView
from corehq.apps.locations.permissions import location_safe


class CaseListFilterUtils(EmwfUtils):

    def sharing_group_tuple(self, g):
        return ("sg__%s" % g['_id'], '%s [case sharing]' % g['name'])

    @property
    @memoized
    def static_options(self):
        options = super(CaseListFilterUtils, self).static_options
        # replace [All mobile workers] with case-list-specific options
        assert options[0][0] == "t__0"
        return [
            ("all_data", _("[All Data]")),
            ('project_data', _("[Project Data]"))
        ] + options[1:]


class CaseListFilter(ExpandedMobileWorkerFilter):
    options_url = 'case_list_options'

    @property
    @memoized
    def utils(self):
        return CaseListFilterUtils(self.domain)

    @staticmethod
    def show_all_data(mobile_user_and_group_slugs):
        return 'all_data' in mobile_user_and_group_slugs

    @staticmethod
    def show_project_data(mobile_user_and_group_slugs):
        return 'project_data' in mobile_user_and_group_slugs

    @staticmethod
    def selected_sharing_group_ids(mobile_user_and_group_slugs):
        return [g[4:] for g in mobile_user_and_group_slugs if g.startswith("sg__")]

    @classmethod
    def selected_group_ids(cls, mobile_user_and_group_slugs):
        return (super(CaseListFilter, cls).selected_group_ids(mobile_user_and_group_slugs) +
                cls.selected_sharing_group_ids(mobile_user_and_group_slugs))

    def _selected_group_entries(self, mobile_user_and_group_slugs):
        query_results = self._selected_groups_query(mobile_user_and_group_slugs)
        reporting = [self.utils.reporting_group_tuple(group)
                     for group in query_results
                     if group.get("reporting", False)]
        sharing = [self.utils.sharing_group_tuple(group)
                   for group in query_results
                   if group.get("case_sharing", False)]
        return reporting + sharing

    def get_default_selections(self):
        return [('project_data', _("[Project Data]"))]


@location_safe
class CaseListFilterOptions(EmwfOptionsView):

    @property
    @memoized
    def utils(self):
        return CaseListFilterUtils(self.domain)

    def get_users(self, query, start, size):
        users = (self.user_es_query(query)
                 .fields(['_id', 'username', 'first_name', 'last_name', 'doc_type'])
                 .start(start)
                 .size(size)
                 .sort("username.exact"))
        if not self.request.can_access_all_locations:
            user_location_id = self.request.couch_user.get_location_id(self.domain)
            all_location_ids = SQLLocation.location_and_descendants_ids([user_location_id])
            users = users.location(all_location_ids)

        return [self.utils.user_tuple(u) for u in users.run().hits]

    @property
    def data_sources(self):
        print 'fetching data source for filters in view'
        locations_own_cases = (LocationType.objects
                               .filter(domain=self.domain, shares_cases=True)
                               .exists())
        sources = [
            (self.get_static_options_size, self.get_static_options),
            (self.get_sharing_groups_size, self.get_sharing_groups),
        ]
        if locations_own_cases:
            sources.append((self.get_locations_size, self.get_locations))
        if self.request.can_access_all_locations:
            sources.append((self.get_groups_size, self.get_groups))
        # appending this in the end to avoid long list of users delaying
        # locations, groups etc in the list on pagination
        sources.append((self.get_users_size, self.get_users))
        return sources

    def get_sharing_groups_size(self, query):
        return self.group_es_query(query, group_type="case_sharing").count()

    def get_sharing_groups(self, query, start, size):
        groups = (self.group_es_query(query, group_type="case_sharing")
                  .fields(['_id', 'name'])
                  .start(start)
                  .size(size)
                  .sort("name.exact"))
        return map(self.utils.sharing_group_tuple, groups.run().hits)

    def get_locations_query(self, query):
        return (SQLLocation.active_objects
                .filter_path_by_user_input(self.domain, query)
                .accessible_to_user(self.request.domain, self.request.couch_user))
