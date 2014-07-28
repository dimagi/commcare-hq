import json
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.care_pathways.api.v0_1 import GeographySqlData


class GeographyFilter(AsyncLocationFilter):
    label = ugettext_noop("Geography")
    slug = "geography"

    @property
    def filter_context(self):
        api_root = reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                        'resource_name': 'geography',
                                                        'api_name': 'v0.5'})
        selected_id = self.request.GET.get('location_id')

        context = {}
        context.update({
            'api_root': api_root,
            'control_name': self.label,
            'control_slug': self.slug,
            'loc_id': selected_id,
            'locations': json.dumps(GeographySqlData(self.domain, selected_id=selected_id).data),
            'hierarchy': [(u'lvl_1', [None]), (u'lvl_2', [u'lvl_1']), (u'lvl_3', [u'lvl_2']), (u'lvl_4', [u'lvl_3']), (u'lvl_5', [u'lvl_4'])]
        })

        return context
