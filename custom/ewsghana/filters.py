import calendar
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.rrule import *
from django.utils.translation import ugettext_noop
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.models import Program
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter, \
    BaseMultipleOptionFilter, BaseReportFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.common import ALL_OPTION
from corehq import Domain
from custom.ewsghana.utils import ews_date_format
import settings


class ProductByProgramFilter(BaseDrilldownOptionFilter):
    slug = "filter_by"
    single_option_select = 0
    template = "common/drilldown_options.html"
    label = ugettext_noop("Filter By")

    @property
    def drilldown_map(self):
        options = [{"val": ALL_OPTION, "text": "All", "next": []}]
        for program in Program.by_domain(self.domain):
            options.append({"val": program.get_id, "text": program.name})
        return options

    @classmethod
    def get_labels(cls):
        return [('Program', 'program')]

    @property
    def filter_context(self):
        controls = []
        for level, label in enumerate(self.rendered_labels):
            controls.append({
                'label': label[0],
                'slug': label[1],
                'level': level,
            })

        return {
            'option_map': self.drilldown_map,
            'controls': controls,
            'selected': self.selected,
            'use_last': self.use_only_last,
            'notifications': self.final_notifications,
            'empty_text': self.drilldown_empty_text,
            'is_empty': not self.drilldown_map,
            'single_option_select': self.single_option_select
        }

    @classmethod
    def _get_label_value(cls, request, label):
        slug = str(label[1])
        val = request.GET.getlist('%s_%s' % (cls.slug, str(label[1])))
        return {
            'slug': slug,
            'value': val,
        }


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


class EWSLocationFilter(AsyncLocationFilter):
    def reporting_types(self):
        return [
            location_type.name
            for location_type in Domain.get_by_name(self.domain).location_types
            if not location_type.administrative
        ]

    @property
    def filter_context(self):
        context = super(EWSLocationFilter, self).filter_context
        hierarchy = []
        for h in context['hierarchy']:
            if h[0] not in self.reporting_types():
                hierarchy.append(h)
        context['hierarchy'] = hierarchy

        return context


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
        years = [dict(val=unicode(y), text=y) for y in range(start_year, datetime.utcnow().year + 1)]
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
                value = '{0}|{1}'.format(val.strftime("%Y-%m-%d"), fridays[idx+1].strftime("%Y-%m-%d"))
                text = '{0} - {1}'.format(ews_date_format(val), ews_date_format(fridays[idx+1]))
            except IndexError:
                value = '{0}|{1}'.format(val.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d"))
                text = '{0} - {1}'.format(ews_date_format(val), ews_date_format(now))
            finally:
                weeks.append(dict(val=value, text=text))
        return [
            {
                'text': 'Month',
                'val': 1,
                'firstOptions': months,
                'secondOptions': years
            },
            {
                'text': 'Week Friday - Thursday',
                'val': 2,
                'firstOptions': weeks,
                'secondOptions': []
            }
        ]

    @property
    def filter_context(self):
        return dict(
            select_options=self.select_options,
            selected_type=self.selected('type') if self.selected('type') else 1,
            selected_first=self.selected('first') if self.selected('first') else datetime.utcnow().month,
            selected_second=self.selected('second') if self.selected('second') else datetime.utcnow().year
        )