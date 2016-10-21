from django.core.urlresolvers import reverse

from corehq.apps.reports.filters.base import BaseMultipleOptionFilter
from corehq.apps.userreports.reports.filters.choice_providers import LocationChoiceProvider
from custom.enikshay.reports.utils import StubReport


from django.utils.translation import ugettext_lazy as _


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
