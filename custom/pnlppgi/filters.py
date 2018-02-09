from __future__ import absolute_import
import datetime

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseDrilldownOptionFilter
from custom.pnlppgi.utils import users_locations
from dimagi.utils.decorators.memoized import memoized
from six.moves import range


class WeekFilter(BaseSingleOptionFilter):
    slug = 'week'
    label = 'Week'

    @property
    @memoized
    def selected(self):
        return self.request.GET.get('week', datetime.datetime.utcnow().isocalendar()[1])

    @property
    def options(self):
        return [(p, p) for p in range(1, 53)]


class LocationBaseDrilldownOptionFilter(BaseDrilldownOptionFilter):
    slug = 'id'
    label = 'Location'

    @classmethod
    def get_labels(cls):
        return [
            ('Zone', 'Select Zone', 'zone'),
            ('Region', 'Select Region', 'region'),
            ('District', 'Select District', 'district'),
            ('Site', 'Select Site', 'site')
        ]

    @property
    @memoized
    def drilldown_map(self):
        user_location = users_locations()
        locations = SQLLocation.objects.filter(
            domain=self.domain,
            location_type__code='zone',
            is_archived=False
        ).order_by('name')
        hierarchy = []
        for zone in locations:
            z = {
                'val': zone.location_id,
                'text': zone.name,
                'next': []
            }
            for reg in zone.children.order_by('name'):
                r = {
                    'val': reg.location_id,
                    'text': reg.name,
                    'next': []
                }
                for dis in reg.children.order_by('name'):
                    d = {
                        'val': dis.location_id,
                        'text': dis.name,
                        'next': []
                    }
                    for site in dis.children.order_by('name'):
                        if site.location_id in user_location:
                            d['next'].append({
                                'val': site.location_id,
                                'text': site.name,
                                'next': []
                            })
                    if len(d['next']) > 0:
                        r['next'].append(d)
                if len(r['next']) > 0:
                    z['next'].append(r)
            if len(z['next']) > 0:
                hierarchy.append(z)
        return hierarchy
