from django.utils.translation import ugettext as _

from dimagi.utils.decorators.memoized import memoized
from corehq.elastic import es_wrapper

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
                return self.utils.sharing_group_tuple(group)
            return self.utils.reporting_group_tuple(group)

        fields = ['_id', 'name']
        groups = self.group_es_call(
            fields=fields,
            sort_by="name.exact",
            order="asc",
            start_at=start,
            size=size,
        )
        return map(wrap_group, groups)
