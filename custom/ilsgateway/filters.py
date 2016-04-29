import calendar
from datetime import datetime
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop
from corehq.apps.products.models import SQLProduct
from corehq.apps.programs.models import Program
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseSingleOptionFilter, BaseReportFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from custom.common import ALL_OPTION


class ProductByProgramFilter(BaseDrilldownOptionFilter):
    slug = "filter_by"
    single_option_select = 0
    template = "common/bootstrap2/drilldown_options.html"
    label = ugettext_noop("Filter By")

    @property
    def drilldown_map(self):
        options = [{"val": ALL_OPTION, "text": "All", "next": []}]
        for program in Program.by_domain(self.domain):
            products = [{"val": ALL_OPTION, "text": "All", "next": []}]
            for product in SQLProduct.objects.filter(domain=self.domain, program_id=program.get_id):
                products.append({"val": product.id, "text": product.name})
            options.append({"val": program.get_id, "text": program.name, "next": products})
        return options

    @classmethod
    def get_labels(cls):
        return [('Program', 'program'), ('Product', 'product')]

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


class ProgramFilter(BaseSingleOptionFilter):
    slug = 'filter_by_program'
    label = 'Program'

    @property
    def options(self):
        return [(p._id, p.name) for p in Program.by_domain(self.domain)]


class ILSDateFilter(BaseReportFilter):

    slug = "datespan"
    label = "Filter By:"
    css_class = 'col-md-4'
    template = 'ilsgateway/bootstrap3/datespan.html'

    def selected(self, type):
        slug = '{0}_{1}'.format(self.slug, type)
        return self.request.GET.get(slug)

    @property
    def select_options(self):
        start_year = getattr(settings, 'START_YEAR', 2008)
        years = [dict(val=unicode(y), text=y) for y in range(start_year, datetime.utcnow().year + 1)]
        years.reverse()
        months = [dict(val="%02d" % m, text=calendar.month_name[m]) for m in range(1, 13)]
        quarters = [dict(val=1, text='Quarter 1'),
                    dict(val=2, text='Quarter 2'),
                    dict(val=3, text='Quarter 3'),
                    dict(val=4, text='Quarter 4')]
        return [
            {
                'text': 'Month',
                'val': 1,
                'firstOptions': months,
                'secondOptions': years
            },
            {
                'text': 'Quarter',
                'val': 2,
                'firstOptions': quarters,
                'secondOptions': years
            },
            {
                'text': 'Year',
                'val': 3,
                'firstOptions': [],
                'secondOptions': years
            }]

    @property
    def filter_context(self):
        return dict(
            select_options=self.select_options,
            selected_type=self.selected('type') if self.selected('type') else 1,
            selected_first=self.selected('first') if self.selected('first') else datetime.utcnow().month,
            selected_second=self.selected('second') if self.selected('second') else datetime.utcnow().year
        )


class B3ILSDateFilter(ILSDateFilter):
    css_class = 'col-md-4'
    template = 'ilsgateway/bootstrap3/datespan.html'


class ILSAsyncLocationFilter(AsyncLocationFilter):

    @property
    def api_root(self):
        return reverse('api_dispatch_list', kwargs={'domain': self.domain,
                                                    'resource_name': 'ils_location',
                                                    'api_name': 'v0.3'})


class B3ILSAsyncLocationFilter(ILSAsyncLocationFilter):
    css_class = 'col-md-8'
    template = 'ilsgateway/bootstrap3/location_async.html'
