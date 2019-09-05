import calendar
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.rrule import *

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_noop

from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.locations.util import location_hierarchy_config, load_locs_json
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.models import Program
from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseMultipleOptionFilter, BaseReportFilter,\
    CheckboxFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.util import reverse
from custom.common import ALL_OPTION
from corehq.apps.domain.models import Domain
from custom.ewsghana.utils import ews_date_format, calculate_last_period


class ProductByProgramFilter(BaseSingleOptionFilter):
    slug = "filter_by_program"
    label = ugettext_noop("Filter By Program")
    default_text = ''

    @property
    def options(self):
        options = [(ALL_OPTION, "All")]
        for program in Program.by_domain(self.domain):
            options.append((program.get_id, program.name))
        return options


class ViewReportFilter(BaseSingleOptionFilter):
    default_text = ugettext_noop("Product Availability")
    slug = 'report_type'
    label = 'View'

    @property
    def options(self):
        return [
            ('stockouts', 'Stockouts'),
            ('asi', 'All Stock Information')
        ]


class ProductFilter(BaseSingleOptionFilter):
    slug = 'product_id'
    label = 'Product'
    default_text = ''

    @property
    def options(self):
        return SQLProduct.objects.filter(domain=self.domain, is_archived=False).values_list('product_id', 'name')\
            .order_by('name')


class MultiProductFilter(BaseMultipleOptionFilter):
    slug = 'product_id'
    label = 'Product'
    default_text = ''

    @property
    def options(self):
        return SQLProduct.objects.filter(domain=self.domain, is_archived=False).values_list('product_id', 'name')\
            .order_by('name')


class EWSRestrictionLocationFilter(AsyncLocationFilter):
    template = "ewsghana/partials/location_async.html"
    only_administrative = False

    @property
    def filter_context(self):
        api_root = reverse('api_dispatch_list',
                           params={'show_administrative': True},
                           kwargs={'domain': self.domain,
                                   'resource_name': 'ews_location',
                                   'api_name': 'v0.3'})
        user = self.request.couch_user
        loc_id = self.request.GET.get('location_id')
        if not loc_id:
            domain_membership = user.get_domain_membership(self.domain)
            if domain_membership:
                loc_id = domain_membership.location_id

        return {
            'api_root': api_root,
            'control_name': self.label,
            'control_slug': self.slug,
            'loc_id': loc_id,
            'locations': load_locs_json(self.domain, loc_id, only_administrative=self.only_administrative),
            'hierarchy': location_hierarchy_config(self.domain)
        }


class EWSLocationFilter(EWSRestrictionLocationFilter):
    only_administrative = True

    def reporting_types(self):
        return [
            location_type.name
            for location_type in Domain.get_by_name(self.domain).location_types
            if not location_type.administrative
        ]

    @property
    def filter_context(self):
        from custom.ewsghana import ROOT_SITE_CODE
        api_root = reverse('api_dispatch_list',
                           params={'show_administrative': False},
                           kwargs={'domain': self.domain,
                                   'resource_name': 'ews_location',
                                   'api_name': 'v0.3'})
        user = self.request.couch_user
        loc_id = self.request.GET.get('location_id')
        if not loc_id:
            domain_membership = user.get_domain_membership(self.domain)
            if not domain_membership or not domain_membership.location_id:
                loc_id = SQLLocation.objects.get(
                    domain=self.domain,
                    site_code=ROOT_SITE_CODE
                ).location_id
            else:
                loc_id = domain_membership.location_id

        location = get_object_or_404(SQLLocation, location_id=loc_id)
        if not location.location_type.administrative:
            loc_id = location.parent.location_id
        hier = location_hierarchy_config(self.domain)
        hierarchy = []
        for h in hier:
            if h[0] not in self.reporting_types():
                hierarchy.append(h)

        return {
            'api_root': api_root,
            'control_name': self.label,
            'control_slug': self.slug,
            'loc_id': loc_id,
            'locations': load_locs_json(self.domain, loc_id, only_administrative=self.only_administrative),
            'hierarchy': hierarchy
        }


class EWSDateFilter(BaseReportFilter):

    template = "ewsghana/datespan.html"
    slug = "datespan"
    label = "Filter By:"

    def selected(self, type):
        slug = '{0}_{1}'.format(self.slug, type)
        return self.request.GET.get(slug)

    @property
    def select_options(self):
        start_year = getattr(settings, 'START_YEAR', 2008)
        years = [dict(val=str(y), text=y) for y in range(start_year, datetime.utcnow().year + 1)]
        years.reverse()
        months = [dict(val="%02d" % m, text=calendar.month_name[m]) for m in range(1, 13)]
        now = datetime.now()
        three_month_earlier = now - relativedelta(months=3)

        first_friday = rrule(DAILY,
                             dtstart=datetime(three_month_earlier.year, three_month_earlier.month, 1),
                             until=now,
                             byweekday=FR)[0]
        if first_friday.day != 1:
            first_friday = first_friday - relativedelta(days=7)
        fridays = rrule(WEEKLY, dtstart=first_friday, until=now, byweekday=FR)
        weeks = []
        value = None
        text = None
        for idx, val in enumerate(fridays):
            try:
                value = '{0}|{1}'.format(val.strftime("%Y-%m-%d"), fridays[idx + 1].strftime("%Y-%m-%d"))
                text = '{0} - {1}'.format(
                    ews_date_format(val),
                    ews_date_format(fridays[idx + 1] - relativedelta(days=1))
                )
            except IndexError:
                next_thursday = val + relativedelta(days=6)
                value = '{0}|{1}'.format(val.strftime("%Y-%m-%d"), next_thursday.strftime("%Y-%m-%d"))
                text = '{0} - {1}'.format(ews_date_format(val), ews_date_format(next_thursday))
            finally:
                weeks.append(dict(val=value, text=text))
        return [
            {
                'text': 'Week (Friday - Thursday)',
                'val': 2,
                'firstOptions': weeks,
                'secondOptions': []
            },
            {
                'text': 'Month',
                'val': 1,
                'firstOptions': months,
                'secondOptions': years
            }

        ]

    @staticmethod
    def last_reporting_period():
        return calculate_last_period()

    @property
    def default_week(self):
        start_date, end_date = self.last_reporting_period()
        return '{0}|{1}'.format(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))

    @property
    def filter_context(self):
        return dict(
            select_options=self.select_options,
            selected_type=self.selected('type') if self.selected('type') else 2,
            selected_first=self.selected('first') if self.selected('first') else self.default_week,
            selected_second=self.selected('second') if self.selected('second') else ''
        )


class LocationTypeFilter(BaseMultipleOptionFilter):
    slug = 'loc_type'
    label = "Location Type"
    placeholder = 'Click to select location type'

    @property
    def options(self):
        return [
            (str(loc_type.pk), loc_type.name) for loc_type in
            LocationType.objects.filter(
                domain=self.domain, administrative=False
            )
        ]


class TransactionCheckboxFilter(CheckboxFilter):
    label = 'Split by product'
    slug = 'split_by_product'
