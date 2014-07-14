import calendar
import json
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop
from corehq.apps.locations.util import location_hierarchy_config, load_locs_json
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import YearFilter, MonthFilter
from corehq.util.translation import localize
from django.utils.translation import ugettext as _


class LocationFilter(AsyncLocationFilter):
    label = ugettext_noop("Region")
    slug = "ih_location_async"
    template = 'intrahealth/location_filter.html'
    required = 0

    @property
    def ctx(self):
        api_root = reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                        'resource_name': 'location',
                                                        'api_name': 'v0.3'})
        selected_loc_id = self.request.GET.get('location_id')

        locations = load_locs_json(self.domain, selected_loc_id)

        if self.required != 2:
            f = lambda y: 'children' in y
            districts = filter(f, locations)
            if districts:
                PPS = filter(f, districts[0]['children'])
                if PPS:
                    del PPS[0]['children']
        return {
            'api_root': api_root,
            'control_name': self.label,
            'control_slug': self.slug,
            'loc_id': selected_loc_id,
            'locations': json.dumps(locations),
            'hierarchy': [loc for loc in location_hierarchy_config(self.domain) if loc[0] != 'PPS'],
        }

    @property
    def filter_context(self):
        context = self.ctx
        context.update(dict(required=self.required))
        return context

class FicheLocationFilter(LocationFilter):
    required = 1

class RecapPassageLocationFilter(LocationFilter):
    required = 2

    @property
    def filter_context(self):
        context = super(RecapPassageLocationFilter, self).filter_context
        context.update(dict(hierarchy=location_hierarchy_config(self.domain)))
        return context

class FRYearFilter(YearFilter):
    label = ugettext_noop(u"Ann\xe9e")


class FRMonthFilter(MonthFilter):
    label = ugettext_noop("Mois")

    @property
    def options(self):
        with localize('fr'):
            return [("%02d" % m, _(calendar.month_name[m])) for m in range(1, 13)]