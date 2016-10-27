from datetime import datetime

from django.core.urlresolvers import reverse

from django.conf import settings

from corehq.apps.reports.filters.base import BaseMultipleOptionFilter, BaseReportFilter
from corehq.apps.userreports.reports.filters.choice_providers import LocationChoiceProvider
from custom.enikshay.reports.utils import StubReport


from django.utils.translation import ugettext_lazy as _

from dimagi.utils.dates import DateSpan


class EnikshayLocationFilter(BaseMultipleOptionFilter):

    label = _('Location')
    slug = 'locations_id'

    @property
    def options(self):
        return []

    @property
    def selected(self):
        selected = super(EnikshayLocationFilter, self).selected
        choice_provider = LocationChoiceProvider(StubReport(domain=self.domain), None)
        choice_provider.configure({'include_descendants': True})
        return [
            {'id': location.value, 'text': location.display}
            for location in choice_provider.get_choices_for_known_values(selected)
        ]

    @property
    def pagination_source(self):
        return reverse('enikshay_locations', kwargs={'domain': self.domain})

    @property
    def filter_context(self):
        context = super(EnikshayLocationFilter, self).filter_context
        context['endpoint'] = self.pagination_source
        return context


class QuarterFilter(BaseReportFilter):
    label = _('Quarter')
    slug = 'datespan'

    template = 'enikshay/filters/quarter_filter.html'

    @property
    def years(self):
        start_year = getattr(settings, 'START_YEAR', 2008)
        years = [(str(y), y) for y in range(start_year, datetime.utcnow().year + 1)]
        years.reverse()
        return years

    @staticmethod
    def default_year():
        return datetime.utcnow().year

    @staticmethod
    def default_quarter():
        return (datetime.utcnow().month / 3) + 1

    @property
    def year(self):
        return self.request.GET.get('datespan-year') or datetime.utcnow().year

    @property
    def quarter(self):
        return self.request.GET.get('datespan-quarter') or (datetime.utcnow().month / 3) + 1

    @property
    def filter_context(self):
        return {
            'years': self.years,
            'year': self.year,
            'quarter': self.quarter
        }

    @classmethod
    def get_value(cls, request, domain):
        try:
            year = int(request.GET.get('datespan-year')) or cls.default_year()
            quarter = int(request.GET.get('datespan-quarter')) or cls.default_quarter()
        except ValueError:
            year = cls.default_year()
            quarter = cls.default_quarter()

        quarter_to_date_dict = {
            1: DateSpan(datetime(year, 1, 1), datetime(year, 4, 1), inclusive=False),
            2: DateSpan(datetime(year, 4, 1), datetime(year, 7, 1), inclusive=False),
            3: DateSpan(datetime(year, 7, 1), datetime(year, 10, 1), inclusive=False),
            4: DateSpan(datetime(year, 10, 1), datetime(year + 1, 1, 1), inclusive=False),
        }
        return quarter_to_date_dict[quarter]
