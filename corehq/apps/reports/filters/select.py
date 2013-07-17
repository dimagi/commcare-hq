from django.utils.translation import ugettext_noop
from corehq.apps.domain.models import Domain
from corehq.apps.reports.filters.base import BaseSingleOptionFilter


class SelectRegionFilter(BaseSingleOptionFilter):
    slug = "region"
    label = ugettext_noop("Region")
    default_text = ugettext_noop("All Regions")

    @property
    def options(self):
        if hasattr(Domain, 'regions'):
            available_regions = [(d.replace(' ', '+'), d) for d in Domain.regions()]
        else:
            available_regions = []
        return available_regions
