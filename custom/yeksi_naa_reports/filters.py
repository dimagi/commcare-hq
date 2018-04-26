# encoding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from django.urls import reverse
from django.utils.translation import ugettext_noop
from corehq.apps.locations.util import location_hierarchy_config, load_locs_json
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter

import json
from corehq.apps.reports.filters.base import BaseReportFilter
import datetime
from six.moves import range


class LocationFilter(AsyncLocationFilter):
    label = ugettext_noop("Location")
    slug = "yeksi_naa_location_async"
    template = 'yeksi_naa/location_filter.html'

    @property
    def filter_context(self):
        api_root = reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                        'resource_name': 'location_internal',
                                                        'api_name': 'v0.5'})
        selected_loc_id = self.request.GET.get('location_id')
        locations = load_locs_json(self.domain, selected_loc_id)

        return {
            'api_root': api_root,
            'control_name': self.label,
            'control_slug': self.slug,
            'loc_id': selected_loc_id if selected_loc_id else '',
            'locations': json.dumps(locations),
            'hierarchy': [loc for loc in location_hierarchy_config(self.domain)],
        }


class MonthsDateFilter(BaseReportFilter):
    template = "yeksi_naa/months_datespan.html"
    slug = 'datespan'
    label = "Plage de dates"

    @classmethod
    def months(cls):
        return [
            {u'name': 'Janvier', u'value': 1}, {u'name': 'Février', u'value': 2},
            {u'name': 'Mars', u'value': 3}, {u'name': 'Avril', u'value': 4},
            {u'name': 'Mai', u'value': 5}, {u'name': 'Juin', u'value': 6},
            {u'name': 'Juillet', u'value': 7}, {u'name': 'Août', u'value': 8},
            {u'name': 'Septembre', u'value': 9}, {u'name': 'Octobre', u'value': 10},
            {u'name': 'Novembre', u'value': 11}, {u'name': 'Décembre', u'value': 12}
        ]

    @property
    def filter_context(self):
        oldest_year = 2016
        return {
            'months': self.months(),
            'years': list(range(oldest_year, datetime.date.today().year + 1)),
            'starting_month': int(self.request.GET.get('month_start', 1)),
            'starting_year': int(self.request.GET.get('year_start', datetime.date.today().year)),
            'current_month': int(self.request.GET.get('month_end', datetime.date.today().month)),
            'current_year': int(self.request.GET.get('year_end', datetime.date.today().year)),
        }
