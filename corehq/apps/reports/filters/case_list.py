from dimagi.utils.decorators.memoized import memoized
from corehq.elastic import es_wrapper

from .users import ExpandedMobileWorkerFilter
from .api import EmwfOptionsView


class CaseListFilterMixin(object):
    additional_options = [("all_data", "[All Data]")]

    def sharing_group_tuple(self, g):
        return ("sg__%s" % g['_id'], '%s [case sharing]' % g['name'])


class CaseListFilter(CaseListFilterMixin, ExpandedMobileWorkerFilter):
    options_url = 'case_list_options'

    @classmethod
    def show_all_data(cls, request):
        emws = request.GET.getlist(cls.slug)
        return 'all_data' in emws

    @property
    @memoized
    def selected(self):
        selected = super(CaseListFilter, self).selected
        if self.show_all_data(self.request):
            selected = [{'id': 'all_data', 'text': "[All Data]"}] + selected
        return selected


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
            print 'wrap_group', group
            print group.get('case_sharing', None), group.get('reporting', None)
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
