from datetime import datetime

from django.core.urlresolvers import reverse

from corehq.apps.reports.filters.base import BaseMultipleOptionFilter, BaseReportFilter, BaseSingleOptionFilter
from corehq.apps.reports_core.exceptions import FilterValueException
from corehq.apps.reports_core.filters import QuarterFilter as UCRQuarterFilter
from corehq.apps.userreports.reports.filters.choice_providers import LocationChoiceProvider
from custom.enikshay.reports.utils import StubReport


from django.utils.translation import ugettext_lazy as _

from dimagi.utils.decorators.memoized import memoized


class EnikshayLocationFilter(BaseMultipleOptionFilter):

    label = _('Location')
    slug = 'locations_id'

    @property
    def options(self):
        return []

    @property
    def selected(self):
        """
        Values returned by this method are displayed in select box
        It should return locations passed in GET parameters without their descendants
        :return: Selected locations without their descendants
        """
        location_ids = self.request.GET.getlist(self.slug)
        choice_provider = LocationChoiceProvider(StubReport(domain=self.domain), None)
        # We don't include descendants here because they will show up in select box
        choice_provider.configure({'include_descendants': False})
        choices = choice_provider.get_choices_for_known_values(location_ids, self.request.couch_user)
        if not choices:
            return self.default_options
        else:
            return [
                {'id': choice.value, 'text': choice.display}
                for choice in choices
            ]

    @classmethod
    def get_value(cls, request, domain):
        selected = super(EnikshayLocationFilter, cls).get_value(request, domain)
        choice_provider = LocationChoiceProvider(StubReport(domain=domain), None)
        choice_provider.configure({'include_descendants': True})
        return [
            choice.value
            for choice in choice_provider.get_choices_for_known_values(selected, request.couch_user)
        ]

    @property
    def pagination_source(self):
        return reverse('enikshay_locations', kwargs={'domain': self.domain})

    @property
    def filter_context(self):
        context = super(EnikshayLocationFilter, self).filter_context
        context['endpoint'] = self.pagination_source
        return context


class EnikshayMigrationFilter(BaseSingleOptionFilter):
    slug = 'is_migrated'
    label = _('Filter migrated data')
    default_text = _('Show All')
    options = (
        ('1', 'Show only migrated from Nikshay'),
        ('0', 'Show only eNikshay'),
    )


class QuarterFilter(BaseReportFilter):
    label = _('Quarter')
    slug = 'datespan'

    template = 'enikshay/filters/quarter_filter.html'

    @classmethod
    @memoized
    def quarter_filter(cls):
        return UCRQuarterFilter(name=cls.slug, label=cls.label, css_id=cls.slug)

    @property
    def years(self):
        return self.quarter_filter().years

    @property
    def default_year(self):
        return datetime.utcnow().year

    @property
    def year(self):
        return self.request.GET.get('datespan-year') or self.default_year

    @property
    def quarter(self):
        return self.request.GET.get('datespan-quarter') or 1

    @property
    def filter_context(self):
        return {
            'context_': {
                'label': self.label
            },
            'filter': {
                'years': self.years,
                'year': self.year,
                'quarter': self.quarter,
                'css_id': self.quarter_filter().css_id
            }

        }

    @classmethod
    def get_value(cls, request, domain):
        year = request.GET.get('datespan-year')
        quarter = request.GET.get('datespan-quarter')

        if not year or not quarter:
            return cls.quarter_filter().default_value()

        try:
            return cls.quarter_filter().value(
                **{
                    'datespan-year': request.GET.get('datespan-year'),
                    'datespan-quarter': request.GET.get('datespan-quarter')
                }
            )
        except FilterValueException:
            return cls.quarter_filter().default_value()
