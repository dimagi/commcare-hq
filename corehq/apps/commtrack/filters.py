from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.commtrack.models import *
from corehq.apps.commtrack.util import *
from corehq.apps.locations.util import defined_location_types
from corehq.apps.reports.filters.base import BaseSingleOptionFilter, BaseMultipleOptionFilter


class ProductFilter(BaseMultipleOptionFilter):
    slug = 'product'
    label = ugettext_noop('Product')
    default_options = ['_all']

    @property
    def options(self):
        choices = sorted((p._id, p.name) for p in Product.by_domain(self.domain))
        choices.insert(0, ('_all', _('All Products')))
        return choices


class LocationTypeFilter(BaseSingleOptionFilter):
    slug = 'agg_type'
    label = ugettext_noop('Aggregate by')
    default_text = ugettext_noop('Choose Location Type...')

    @property
    def options(self):
        return [(k, k) for k in defined_location_types(self.domain)]
