from django.conf import settings

from dimagi.utils.couch.database import iter_docs

from corehq.apps.commtrack.helpers import make_supply_point
from corehq.apps.commtrack.models import SupplyPointCase
from corehq.form_processor.abstract_models import AbstractSupplyInterface


class SupplyPointCouch(AbstractSupplyInterface):

    @classmethod
    def get_or_create_by_location(cls, location):
        sp = location.linked_supply_point()
        if not sp:
            sp = make_supply_point(location.domain, location)
        return sp

    @classmethod
    def get_by_location(cls, location):
        return location.linked_supply_point()

    @staticmethod
    def get_closed_and_open_by_location_id_and_domain(domain, location_id):
        return SupplyPointCase.view(
            'supply_point_by_loc/view',
            key=[domain, location_id],
            include_docs=True,
            classes={'CommCareCase': SupplyPointCase},
            limit=1,
        ).one()

    @staticmethod
    def get_supply_point(supply_point_id):
        return SupplyPointCase.get(supply_point_id)

    @staticmethod
    def get_supply_points(supply_point_ids):
        supply_points = []
        for doc in iter_docs(SupplyPointCase.get_db(), supply_point_ids):
            supply_points.append(SupplyPointCase.wrap(doc))
        return supply_points
