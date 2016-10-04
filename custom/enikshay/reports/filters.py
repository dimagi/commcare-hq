from django.core.urlresolvers import reverse

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.filters.base import BaseMultipleOptionFilter


class EnikshayLocationFilter(BaseMultipleOptionFilter):

    label = 'Location'
    slug = 'locations_id'

    @property
    def options(self):
        return []

    @property
    def selected(self):
        return [
            {'id': location.location_id, 'text': location.display_name}
            for location in SQLLocation.objects.filter(
                domain=self.domain,
                location_id__in=super(EnikshayLocationFilter, self).selected
            )
        ]

    @property
    def pagination_source(self):
        return reverse('enikshay_locations', kwargs={'domain': self.domain})

    @property
    def filter_context(self):
        context = super(EnikshayLocationFilter, self).filter_context
        context['endpoint'] = self.pagination_source
        return context
