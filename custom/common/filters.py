from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict

from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter


class RestrictedLocationDrillDown(object):

    def __init__(self, domain, user):
        self.domain = domain
        self.user = user

    def get_locations_json(self):
        def loc_to_json(loc):
            return {
                'pk': loc.pk,
                'name': loc.name,
                'location_type': loc.location_type.name,
                'uuid': loc.location_id,
                'is_archived': loc.is_archived,
                'level': loc.level,
                'parent_id': loc.parent_id
            }
        user = self.user

        user_locations = SQLLocation.objects.get_queryset_ancestors(
            SQLLocation.objects.accessible_to_user(self.domain, user),
            include_self=True
        )
        if not user_locations:
            return []

        user_locations = [
            loc_to_json(sql_location)
            for sql_location in user_locations
        ]

        parent_to_location_map = defaultdict(list)

        for location in user_locations:
            parent_to_location_map[location['parent_id']].append(location)

        for location in user_locations:
            location['children'] = parent_to_location_map[location['pk']]

        min_level = min([location['level'] for location in user_locations])
        return [x for x in user_locations if x['level'] == min_level]


class RestrictedAsyncLocationFilter(AsyncLocationFilter):

    def load_locations_json(self, loc_id):
        user = self.request.couch_user
        if user.has_permission(self.domain, 'access_all_locations'):
            return super(RestrictedAsyncLocationFilter, self).load_locations_json(loc_id)
        return RestrictedLocationDrillDown(domain=self.domain, user=user).get_locations_json()
