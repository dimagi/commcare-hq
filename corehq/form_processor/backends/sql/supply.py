from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.abstract_models import AbstractSupplyInterface
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL


class SupplyPointSQL(AbstractSupplyInterface):

    @classmethod
    def get_or_create_by_location(cls, location):
        sp = SupplyPointSQL.get_by_location(location)
        if not sp:
            sp = make_supply_point(location.domain, location)
        return sp

    @classmethod
    def get_by_location(cls, location):
        return location.linked_supply_point()

    @staticmethod
    def get_closed_and_open_by_location_id_and_domain(domain, location_id):
        return CaseAccessorSQL.get_case_by_location(domain, location_id)

    @staticmethod
    def get_supply_point_ids_by_location(domain):
        return dict(SQLLocation.objects.filter(
            domain=domain,
            supply_point_id__isnull=False,
        ).values_list("location_id", "supply_point_id"))

    @staticmethod
    def get_supply_point(supply_point_id):
        return CaseAccessorSQL.get_case(supply_point_id)

    @staticmethod
    def get_supply_points(supply_point_ids):
        return list(CaseAccessorSQL.get_cases(supply_point_ids))
