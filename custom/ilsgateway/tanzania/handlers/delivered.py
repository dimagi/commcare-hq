from datetime import datetime
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import DELIVERY_CONFIRM_DISTRICT, DELIVERY_PARTIAL_CONFIRM, \
    DELIVERY_CONFIRM_CHILDREN


class DeliveredHandler(KeywordHandler):

    def _send_delivery_alert_to_facilities(self, location):
        locs = [c.get_id for c in location.children]
        users = []
        for location_id in locs:
            users.extend(get_users_by_location_id(self.domain, location_id))

        for user in users:
            if user.get_verified_number():
                send_sms_to_verified_number(user.get_verified_number(), DELIVERY_CONFIRM_CHILDREN %
                                            {"district_name": location.name})

    def handle(self):
        location = self.user.location
        SupplyPointStatus.objects.create(location_id=location.get_id,
                                         status_type=SupplyPointStatusTypes.DELIVERY_FACILITY,
                                         status_value=SupplyPointStatusValues.RECEIVED,
                                         status_date=datetime.utcnow())
        return False

    def help(self):
        location = self.user.location
        if not location:
            return False
        status_type = None
        if location.location_type == 'FACILITY':
            status_type = SupplyPointStatusTypes.DELIVERY_FACILITY
            self.respond(DELIVERY_PARTIAL_CONFIRM)
        elif location.location_type == 'DISTRICT':
            status_type = SupplyPointStatusTypes.DELIVERY_DISTRICT
            self._send_delivery_alert_to_facilities(location)
            self.respond(DELIVERY_CONFIRM_DISTRICT, contact_name=self.user.first_name + " " + self.user.last_name,
                         facility_name=location.name)
        SupplyPointStatus.objects.create(location_id=location.get_id,
                                         status_type=status_type,
                                         status_value=SupplyPointStatusValues.RECEIVED,
                                         status_date=datetime.utcnow())
        return True
