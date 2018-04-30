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

from custom.yeksi_naa_reports.sqldata import ProgramData


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
            {'name': 'Janvier', 'value': 1}, {'name': 'Février', 'value': 2},
            {'name': 'Mars', 'value': 3}, {'name': 'Avril', 'value': 4},
            {'name': 'Mai', 'value': 5}, {'name': 'Juin', 'value': 6},
            {'name': 'Juillet', 'value': 7}, {'name': 'Août', 'value': 8},
            {'name': 'Septembre', 'value': 9}, {'name': 'Octobre', 'value': 10},
            {'name': 'Novembre', 'value': 11}, {'name': 'Décembre', 'value': 12}
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


class ProgramFilter(BaseReportFilter):
    template = "yeksi_naa/program_filter.html"
    slug = 'program'
    label = "Programme"

    @classmethod
    def program(cls):
        program_filter = [{
            'name': 'All',
            'value': "%%",
        }]
        programs = ProgramData(config={'domain': 'test-pna'}).rows
        for program in programs:
            program_filter.append({
                'name': program[1],
                'value': "%{0}%".format(program[0]),
            })
        return program_filter

    @property
    def filter_context(self):
        return {
            'programs': self.program(),
            'chosen_program': self.request.GET.get('program', ''),
        }
