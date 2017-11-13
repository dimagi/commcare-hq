from __future__ import absolute_import
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.locations.models import SQLLocation
from .users import ExpandedMobileWorkerFilter
from .api import EmwfOptionsView
from django.urls import reverse
from django.utils.translation import ugettext_lazy


class LocationGroupFilter(ExpandedMobileWorkerFilter):
    """
    Displays a list of locations and groups to select from to filter report
    """
    slug = "grouplocationfilter"
    label = ugettext_lazy("Groups or Locations")
    default_options = None
    placeholder = ugettext_lazy(
        "Click here to select groups or locations to filter in the report")
    is_cacheable = False
    options_url = 'grouplocationfilter_options'

    @property
    @memoized
    def selected(self):
        selected_ids = self.request.GET.getlist(self.slug)

        selected = (self._selected_group_entries(selected_ids) +
                    self._selected_location_entries(selected_ids))
        known_ids = dict(selected)

        return [
            {'id': id, 'text': known_ids[id]}
            for id in selected_ids
            if id in known_ids
        ]

    @property
    def filter_context(self):
        context = super(LocationGroupFilter, self).filter_context
        url = reverse(self.options_url, args=[self.domain])
        context.update({'endpoint': url})
        return context

    @property
    def options(self):
        return [
            (location.location_id, location.name) for location in
            SQLLocation.objects.filter(domain=self.domain)
        ]


class LocationGroupFilterOptions(EmwfOptionsView):

    @property
    def data_sources(self):
        # data sources for options for selection in filter
        # when searcing for custom locations search limit to just locations
        if self.custom_locations_search():
            return [(self.get_locations_size, self.get_locations)]
        return [
            (self.get_groups_size, self.get_groups),
            (self.get_locations_size, self.get_locations),
        ]
