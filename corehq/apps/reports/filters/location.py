from django.utils.translation import ugettext as _

from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import SQLLocation
from .base import BaseMultipleOptionFilter
from .users import EmwfUtils
from .api import EmwfOptionsView
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy
from corehq import toggles


class LocationGroupFilter(BaseMultipleOptionFilter):
    slug = "grouplocationfilter"
    label = ugettext_lazy("Groups or Locations")
    default_options = None
    placeholder = ugettext_lazy(
        "Specify groups and users to include in the report")
    is_cacheable = False
    options_url = 'grouplocationfilter_options'

    @property
    @memoized
    def utils(self):
        return EmwfUtils(self.domain)

    @property
    def filter_context(self):
        context = super(LocationGroupFilter, self).filter_context
        url = reverse(self.options_url, args=[self.domain])
        context.update({'endpoint': url})
        return context

    @staticmethod
    def selected_location_ids(mobile_user_and_group_slugs):
        return [l[3:] for l in mobile_user_and_group_slugs if l.startswith("l__")]

    def _selected_location_entries(self, mobile_user_and_group_slugs):
        location_ids = self.selected_location_ids(mobile_user_and_group_slugs)
        if not location_ids:
            return []
        return map(self.utils.location_tuple,
                   SQLLocation.objects.filter(location_id__in=location_ids))

    @property
    def options(self):
        return [
            (location.location_id, location.name) for location in
            SQLLocation.objects.filter(domain=self.domain)
        ]

    @classmethod
    def for_reporting_group(cls, group_id):
        return {
            cls.slug: 'g__%s' % group_id
        }


class LocationGroupFilterOptions(EmwfOptionsView):

    @property
    def data_sources(self):
        if toggles.LOCATIONS_IN_REPORTS.enabled(self.domain):
            return [
                (self.get_groups_size, self.get_groups),
                (self.get_locations_size, self.get_locations),
            ]
        else:
            return [
                (self.get_groups_size, self.get_groups),
            ]
