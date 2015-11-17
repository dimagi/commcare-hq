from dimagi.utils.decorators.memoized import memoized

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

    @property
    @memoized
    def case_model(self):
        from casexml.apps.case.models import CommCareCase
        from corehq.form_processor.models import CommCareCaseSQL
        if should_use_sql_backend(self.domain):
            return CommCareCaseSQL
        else:
            return CommCareCase

    def get_or_create_by_location(self, location):
        return self.supply_point.get_or_create_by_location(location)

    def get_by_location(self, location):
        return self.supply_point.get_by_location(location)

    def get_supply_point(self, supply_point_id):
        return self.case_model.get(supply_point_id)
