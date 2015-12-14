from django.utils.translation import ugettext as _

from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import LocationType

from .users import ExpandedMobileWorkerFilter, EmwfUtils
from .api import EmwfOptionsView


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

    @classmethod
    def show_all_data(cls, mobile_user_and_group_slugs):
        return 'all_data' in mobile_user_and_group_slugs

    @classmethod
    def show_project_data(cls, mobile_user_and_group_slugs):
        return 'project_data' in mobile_user_and_group_slugs

    @classmethod
    def selected_sharing_group_ids(cls, mobile_user_and_group_slugs):
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


class CaseListFilterOptions(EmwfOptionsView):
    @property
    @memoized
    def utils(self):
        return CaseListFilterUtils(self.domain)

    @property
    def data_sources(self):
        locations_own_cases = (LocationType.objects
                               .filter(domain=self.domain, shares_cases=True)
                               .exists())
        if locations_own_cases:
            return [
                (self.get_static_options_size, self.get_static_options),
                (self.get_groups_size, self.get_groups),
                (self.get_sharing_groups_size, self.get_sharing_groups),
                (self.get_locations_size, self.get_locations),
                (self.get_users_size, self.get_users),
            ]
        else:
            return [
                (self.get_static_options_size, self.get_static_options),
                (self.get_groups_size, self.get_groups),
                (self.get_sharing_groups_size, self.get_sharing_groups),
                (self.get_users_size, self.get_users),
            ]

    def get_sharing_groups_size(self, query):
        return self.group_es_call(query, group_type="case_sharing", size=0,
                                  return_count=True)[0]

    def get_sharing_groups(self, query, start, size):
        fields = ['_id', 'name']
        sharing_groups = self.group_es_call(
            query,
            group_type="case_sharing",
            fields=fields,
            sort_by="name.exact",
            order="asc",
            start_at=start,
            size=size,
        )
        return map(self.utils.sharing_group_tuple, sharing_groups)
