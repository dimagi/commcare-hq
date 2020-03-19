from corehq.apps.reports.filters.fixtures import AsyncLocationFilter


class RestrictedAsyncLocationFilter(AsyncLocationFilter):

    def load_locations_json(self, loc_id):
        user = self.request.couch_user
        if user.has_permission(self.domain, 'access_all_locations'):
            return super(RestrictedAsyncLocationFilter, self).load_locations_json(loc_id)
        return RestrictedLocationDrillDown(domain=self.domain, user=user).get_locations_json()
