from __future__ import absolute_import
from corehq.apps.commtrack.util import get_supply_point
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation


class BulkCacheBase(object):
    def __init__(self, domain):
        self.domain = domain
        self.cache = {}

    def get(self, key):
        if not key:
            return None
        if key not in self.cache:
            self.cache[key] = self.lookup(key)
        return self.cache[key]

    def lookup(self, key):
        # base classes must implement this themselves
        raise NotImplementedError


class SiteCodeToLocationCache(BulkCacheBase):
    def __init__(self, domain):
        self.non_admin_types = [
            loc_type.name for loc_type in Domain.get_by_name(domain).location_types
            if not loc_type.administrative
        ]
        return super(SiteCodeToLocationCache, self).__init__(domain)

    def lookup(self, site_code):
        return SQLLocation.objects.get(
            domain=self.domain,
            site_code=site_code
        ).couch_location


class SiteCodeToSupplyPointCache(BulkCacheBase):
    """
    Cache the lookup of a supply point object from
    the site code used in upload.
    """

    def lookup(self, site_code):
        supply_point = get_supply_point(
            self.domain,
            site_code
        )['case']
        return supply_point


class LocationIdToSiteCodeCache(BulkCacheBase):
    def lookup(self, location_id):
        return SQLLocation.objects.get(
            domain=self.domain,  # this is only for safety
            location_id=location_id
        ).site_code
