from __future__ import absolute_import
from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.reports.filters.choice_providers import LocationChoiceProvider


class DistrictChoiceProvider(LocationChoiceProvider):
    def _locations_query(self, query_text, user):
        active_locations = SQLLocation.active_objects
        if query_text:
            return active_locations.filter_by_user_input(
                domain=self.domain,
                user_input=query_text
            ).accessible_to_user(self.domain, user).filter(location_type__code__exact='dto')
        return active_locations.accessible_to_user(self.domain, user).filter(
            domain=self.domain, location_type__code__exact='dto',)

    def get_choices_for_known_values(self, values, user):
        selected_locations = self._locations_query(None, user).filter(location_id__in=values)
        return self._locations_to_choices(selected_locations)
