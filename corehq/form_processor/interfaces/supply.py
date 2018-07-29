from __future__ import absolute_import
from __future__ import unicode_literals
from memoized import memoized

from ..utils import should_use_sql_backend


class SupplyInterface(object):

    def __init__(self, domain=None):
        self.domain = domain

    @classmethod
    def create_from_location(cls, domain, location):
        from corehq.apps.commtrack.helpers import make_supply_point
        return make_supply_point(domain, location)

    @property
    @memoized
    def supply_point(self):
        from corehq.form_processor.backends.couch.supply import SupplyPointCouch
        from corehq.form_processor.backends.sql.supply import SupplyPointSQL
        if should_use_sql_backend(self.domain):
            return SupplyPointSQL
        else:
            return SupplyPointCouch

    def get_or_create_by_location(self, location):
        return self.supply_point.get_or_create_by_location(location)

    def get_by_location(self, location):
        return self.supply_point.get_by_location(location)

    def get_closed_and_open_by_location_id_and_domain(self, domain, location_id):
        """
        This also returns closed supply points.
        Please use location.linked_supply_point() instead.
        """
        return self.supply_point.get_closed_and_open_by_location_id_and_domain(domain, location_id)

    def get_supply_point(self, supply_point_id):
        return self.supply_point.get_supply_point(supply_point_id)

    def get_supply_points(self, supply_point_ids):
        return self.supply_point.get_supply_points(supply_point_ids)
