import json
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop
from corehq.apps.locations.util import load_locs_json, location_hierarchy_config
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter


class LocationFilter(AsyncLocationFilter):
    label = ugettext_noop("Region")
    slug = "ih_location_async"
    template = 'intrahealth/location_filter.html'

    @property
    def filter_context(self):
        api_root = reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                        'resource_name': 'location',
                                                        'api_name': 'v0.3'})
        selected_loc_id = self.request.GET.get('location_id')
        return {
            'api_root': api_root,
            'control_name': self.label,
            'control_slug': self.slug,
            'loc_id': selected_loc_id,
            'locations': json.dumps(load_locs_json(self.domain, selected_loc_id)),
            'hierarchy': [loc for loc in location_hierarchy_config(self.domain) if loc[0] != 'PPS'],
        }