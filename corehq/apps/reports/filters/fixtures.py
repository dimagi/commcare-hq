import json
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.locations.util import load_locs_json, location_hierarchy_config
from corehq.apps.reports.filters.base import BaseReportFilter


class AsyncDrillableFilter(BaseReportFilter):
    # todo: add documentation
    # todo: cleanup template
    """
    example_hierarchy = [{"type": "state", "display": "name"},
                         {"type": "district", "parent_ref": "state_id", "references": "id", "display": "name"},
                         {"type": "block", "parent_ref": "district_id", "references": "id", "display": "name"},
                         {"type": "village", "parent_ref": "block_id", "references": "id", "display": "name"}]
    """
    template = "reports/filters/drillable_async.html"
    hierarchy = [] # a list of fixture data type names that representing different levels of the hierarchy. Starting with the root

    def fdi_to_json(self, fdi):
        return {
            'fixture_type': fdi.data_type_id,
            'fields': fdi.fields_without_attributes,
            'id': fdi.get_id,
            'children': getattr(fdi, '_children', None),
        }

    fdts = {}
    def data_types(self, index=None):
        if not self.fdts:
            self.fdts = [FixtureDataType.by_domain_tag(self.domain, h["type"]).one() for h in self.hierarchy]
        return self.fdts if index is None else self.fdts[index]

    @property
    def api_root(self):
        return reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                        'resource_name': 'fixture',
                                                        'api_name': 'v0.1'})

    @property
    def full_hierarchy(self):
        ret = []
        for i, h in enumerate(self.hierarchy):
            new_h = dict(h)
            new_h['id'] = self.data_types(i).get_id
            ret.append(new_h)
        return ret

    def generate_lineage(self, leaf_type, leaf_item_id):
        leaf_fdi = FixtureDataItem.get(leaf_item_id)

        index = None
        for i, h in enumerate(self.hierarchy[::-1]):
            if h["type"] == leaf_type:
                index = i

        if index is None:
            raise Exception(
                "Could not generate lineage for AsyncDrillableField due to a nonexistent leaf_type (%s)" % leaf_type)

        lineage = [leaf_fdi]
        for i, h in enumerate(self.full_hierarchy[::-1]):
            if i < index or i >= len(self.hierarchy)-1:
                continue
            real_index = len(self.hierarchy) - (i+1)
            lineage.insert(0, FixtureDataItem.by_field_value(self.domain, self.data_types(real_index - 1),
                h["references"], lineage[0].fields_without_attributes[h["parent_ref"]]).one())

        return lineage

    @property
    def filter_context(self):
        root_fdis = [self.fdi_to_json(f) for f in FixtureDataItem.by_data_type(self.domain, self.data_types(0).get_id)]

        f_id = self.request.GET.get('fixture_id', None)
        selected_fdi_type = f_id.split(':')[0] if f_id else None
        selected_fdi_id = f_id.split(':')[1] if f_id else None

        if selected_fdi_id:
            index = 0
            lineage = self.generate_lineage(selected_fdi_type, selected_fdi_id)
            parent = {'children': root_fdis}
            for i, fdi in enumerate(lineage[:-1]):
                this_fdi = [f for f in parent['children'] if f['id'] == fdi.get_id][0]
                next_h = self.hierarchy[i+1]
                this_fdi['children'] = [self.fdi_to_json(f) for f in FixtureDataItem.by_field_value(self.domain,
                                        self.data_types(i+1), next_h["parent_ref"], fdi.fields_without_attributes[next_h["references"]])]
                parent = this_fdi

        return {
            'api_root': self.api_root,
            'control_name': self.label,
            'control_slug': self.slug,
            'selected_fdi_id': selected_fdi_id,
            'fdis': json.dumps(root_fdis),
            'hierarchy': self.full_hierarchy
        }


class AsyncLocationFilter(BaseReportFilter):
    # todo: cleanup template
    label = ugettext_noop("Location")
    slug = "location_async"
    template = "reports/filters/location_async.html"

    @property
    def filter_context(self):
        api_root = reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                        'resource_name': 'location',
                                                        'api_name': 'v0.3'})
        selected_loc_id = self.request.GET.get('location_id')

        return {
            'api_root': api_root,
            'control_name': self.label, # todo: cleanup, don't follow this structure
            'control_slug': self.slug, # todo: cleanup, don't follow this structure
            'loc_id': selected_loc_id,
            'locations': json.dumps(load_locs_json(self.domain, selected_loc_id)),
            'hierarchy': location_hierarchy_config(self.domain),
        }

class MultiLocationFilter(AsyncDrillableFilter):
    template = "reports/filters/multi_location.html"
