import logging

from corehq.apps.commtrack.helpers import make_supply_point
from corehq.form_processor.abstract_models import AbstractSupplyInterface
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL


class SupplyPointSQL(AbstractSupplyInterface):

    @classmethod
    def get_or_create_by_location(cls, location):
        sp = SupplyPointSQL.get_by_location(location)
        if not sp:
            sp = make_supply_point(location.domain, location)

            # todo: if you come across this after july 2015 go search couchlog
            # and see how frequently this is happening.
            # if it's not happening at all we should remove it.
            logging.warning('supply_point_dynamically_created, {}, {}, {}'.format(
                location.name,
                sp.case_id,
                location.domain,
            ))

        return sp

    @classmethod
    def get_by_location(cls, location):
        return location.linked_supply_point()

    @staticmethod
    def get_closed_and_open_by_location_id_and_domain(domain, location_id):
        return CaseAccessorSQL.get_case_by_location(domain, location_id)

    @staticmethod
    def get_supply_point(supply_point_id):
        return CaseAccessorSQL.get_case(supply_point_id)

    @staticmethod
    def get_supply_points(supply_point_ids):
        return list(CaseAccessorSQL.get_cases(supply_point_ids))
