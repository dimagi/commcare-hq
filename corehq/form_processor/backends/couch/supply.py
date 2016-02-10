import logging

from corehq.apps.commtrack.helpers import make_supply_point
from corehq.form_processor.abstract_models import AbstractSupplyInterface


class SupplyPointCouch(AbstractSupplyInterface):

    @classmethod
    def get_or_create_by_location(cls, location):
        sp = location.linked_supply_point()
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
