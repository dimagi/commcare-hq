# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
import calendar
from datetime import datetime
from corehq.apps.locations.models import get_location
from corehq.apps.reports.standard import MonthYearMixin
from corehq.util.translation import localize
from django.utils.translation import ugettext as _
from memoized import memoized
from dimagi.utils.parsing import json_format_date
from six.moves import range


def get_localized_months():
    #Returns chronological list of months in french language
    with localize('fr'):
        return [(_(calendar.month_name[i])).title() for i in range(1, 13)]


class YeksiNaaMonthYearMixin(MonthYearMixin):
    @property
    def month(self):
        if 'month' in self.request.GET:
            return int(self.request.GET['month'])
        else:
            return datetime.utcnow().month

    @property
    def year(self):
        if 'year' in self.request.GET:
            return int(self.request.GET['year'])
        else:
            return datetime.utcnow().year


class IntraHealthLocationMixin(object):

    @property
    @memoized
    def location(self):
        if self.request.GET.get('location_id'):
            return get_location(self.request.GET.get('location_id'))


class IntraHealthReportConfigMixin(object):

    def config_update(self, config):
        if self.request.GET.get('location_id', ''):
            if self.location.location_type_name.lower() == 'district':
                config.update(dict(district_id=self.location.location_id))
            else:
                config.update(dict(region_id=self.location.location_id))

    @property
    def report_config(self):
        config = dict(
            domain=self.domain,
            startdate=self.datespan.startdate.replace(hour=0, minute=0, second=0),
            enddate=self.datespan.enddate.replace(hour=23, minute=59, second=59),
            visit="''",
            strsd=json_format_date(self.datespan.startdate),
            stred=json_format_date(self.datespan.enddate),
            empty_prd_code='__none__',
            zero=0
        )
        self.config_update(config)
        return config
