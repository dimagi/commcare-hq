from django.utils.translation import ugettext as _

from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import SQLLocation
from corehq.elastic import es_wrapper

from .users import ExpandedMobileWorkerFilter, EmwfUtils
from .api import EmwfOptionsView


class CaseListFilterUtils(EmwfUtils):
    def sharing_group_tuple(self, g):
        return ("sg__%s" % g['_id'], '%s [case sharing]' % g['name'])

    def sharing_location_tuple(self, loc_group):
        return (loc_group._id, loc_group.name + ' [case sharing]')

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
    def show_all_data(cls, request):
        emws = request.GET.getlist(cls.slug)
        return 'all_data' in emws

    @classmethod
    def show_project_data(cls, request):
        emws = request.GET.getlist(cls.slug)
        return 'project_data' in emws

    @classmethod
    def selected_sharing_group_ids(cls, request):
        emws = request.GET.getlist(cls.slug)
        return [g[4:] for g in emws if g.startswith("sg__")]

    @classmethod
    def selected_group_ids(cls, request):
        return (super(CaseListFilter, cls).selected_group_ids(request) +
                cls.selected_sharing_group_ids(request))

    @classmethod
    def selected_sharing_location_ids(cls, request):
        emws = request.GET.getlist(cls.slug)
        return SQLLocation.objects.filter(
            location_id__in=emws,
            is_archived=False
        ).values_list('location_id', flat=True)

    def selected_location_entries(self, request):
        selected = super(CaseListFilter, self).selected_location_entries(request)
        location_sharing_ids = self.selected_sharing_location_ids(self.request)
        if location_sharing_ids:
            locs = SQLLocation.objects.filter(
                location_id__in=location_sharing_ids
            )
            for loc in locs:
                loc_group = loc.case_sharing_group_object()
                selected.append(self.utils.sharing_location_tuple(loc_group))
        return selected

    def selected_group_entries(self, request):
        query_results = self.selected_groups_query(request)
        reporting = [self.utils.reporting_group_tuple(group['fields'])
                     for group in query_results
                     if group['fields'].get("reporting", False)]
        sharing = [self.utils.sharing_group_tuple(group['fields'])
                   for group in query_results
                   if group['fields'].get("case_sharing", False)]
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
        return [
            (self.get_static_options_size, self.get_static_options),
            (self.get_groups_size, self.get_groups),
            (self.get_sharing_groups_size, self.get_sharing_groups),
            (self.get_locations_size, self.get_locations),
            (self.get_sharing_locations_size, self.get_sharing_locations),
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

    def get_sharing_locations_query(self, query):
        return (self.get_locations_query(query)
                    .filter(location_type__shares_cases=True))

    def get_sharing_locations(self, query, start, size):
        for loc in self.get_sharing_locations_query(query)[start:size]:
            group = loc.case_sharing_group_object()
            yield self.utils.sharing_location_tuple(group)

    def get_sharing_locations_size(self, query):
        return self.get_sharing_locations_query(query).count()
