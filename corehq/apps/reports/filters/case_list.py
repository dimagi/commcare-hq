from django.utils.translation import ugettext as _

from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import SQLLocation
from corehq.elastic import es_wrapper

from .users import ExpandedMobileWorkerFilter
from .api import EmwfOptionsView


class CaseListFilterMixin(object):
    def sharing_group_tuple(self, g):
        return ("sg__%s" % g['_id'], '%s [case sharing]' % g['name'])

    def sharing_location_tuple(self, loc_group):
        return (loc_group._id, loc_group.name + ' [case sharing]')

    @property
    @memoized
    def static_options(self):
        options = super(CaseListFilterMixin, self).static_options
        # replace [All mobile workers] with case-list-specific options
        assert options[0][0] == "t__0"
        return [
            ("all_data", _("[All Data]")),
            ('project_data', _("[Project Data]"))
        ] + options[1:]


class CaseListFilter(CaseListFilterMixin, ExpandedMobileWorkerFilter):
    options_url = 'case_list_options'

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
        return super(CaseListFilter, cls).selected_group_ids(request) + \
               cls.selected_sharing_group_ids(request)

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
                selected.append(self.sharing_location_tuple(loc_group))
        return selected

    def selected_group_entries(self, request):
        query_results = self.selected_groups_query(request)
        reporting = [self.reporting_group_tuple(group['fields'])
                     for group in query_results
                     if group['fields'].get("reporting", False)]
        sharing = [self.sharing_group_tuple(group['fields'])
                   for group in query_results
                   if group['fields'].get("case_sharing", False)]
        return reporting + sharing

    def get_default_selections(self):
        return [('project_data', _("[Project Data]"))]


class CaseListFilterOptions(CaseListFilterMixin, EmwfOptionsView):
    def group_es_call(self, group_type=None, **kwargs):
        # Valid group_types are "reporting" and "case_sharing"
        if group_type is None:
            type_filter = {"or": [
                {"term": {"reporting": "true"}},
                {"term": {"case_sharing": "true"}}
            ]}
        else:
            type_filter = {"term": {group_type: "true"}}
        return es_wrapper('groups', domain=self.domain, q=self.group_query,
                          filters=[type_filter], doc_type='Group', **kwargs)

    def get_groups(self, start, size):
        def wrap_group(group):
            if group.get('case_sharing', None):
                return self.sharing_group_tuple(group)
            return self.reporting_group_tuple(group)

        fields = ['_id', 'name']
        groups = self.group_es_call(
            fields=fields,
            sort_by="name.exact",
            order="asc",
            start_at=start,
            size=size,
        )
        return map(wrap_group, groups)

    @property
    def case_sharing_locations_query(self):
        return self.locations_query.filter(location_type__shares_cases=True)

    def get_location_groups(self):
        for location in super(CaseListFilterOptions, self).get_location_groups():
            yield location

        # filter out any non case share type locations for this part
        for loc in self.case_sharing_locations_query:
            group = loc.case_sharing_group_object()
            yield (group._id, group.name + ' [case sharing]')

    def get_locations_size(self):
        return (self.locations_query.count() +
                self.case_sharing_locations_query.count())
