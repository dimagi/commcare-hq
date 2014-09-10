from datetime import datetime
from corehq.apps.commtrack.models import CommTrackUser
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ilsgateway.handlers import get_location
from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.reminders import DELIVERY_CONFIRM_DISTRICT, DELIVERY_PARTIAL_CONFIRM, DELIVERY_CONFIRM_CHILDREN


class DeliveredHandler(KeywordHandler):

    def _send_delivery_alert_to_facilities(self, sp_name, location):
        locs = [c._id for c in location.children]
        users = filter(lambda u: u.domain_membership["location_id"] in locs, CommTrackUser.by_domain(self.domain))
        for user in users:
            if user.get_verified_number():
                send_sms_to_verified_number(user.get_verified_number(), DELIVERY_CONFIRM_CHILDREN % {"district_name": sp_name})

    def handle(self):
        location = get_location(self.domain, self.user, None)
        SupplyPointStatus.objects.create(supply_point=location['case']._id,
                                         status_type=SupplyPointStatusTypes.DELIVERY_FACILITY,
                                         status_value=SupplyPointStatusValues.RECEIVED,
                                         status_date=datetime.utcnow())

    def help(self):
        location = get_location(self.domain, self.user, None)
        status_type = None
        if location['location'].location_type == 'FACILITY':
            status_type = SupplyPointStatusTypes.DELIVERY_FACILITY
            self.respond(DELIVERY_CONFIRM_DISTRICT, contact_name=self.user.first_name + " " + self.user.last_name,
                         facility_name=location['case'].name)
        elif location['location'].location_type == 'DISTRICT':
            status_type = SupplyPointStatusTypes.DELIVERY_DISTRICT
            self._send_delivery_alert_to_facilities(location['case'].name, location['location'])
            self.respond(DELIVERY_PARTIAL_CONFIRM)
        SupplyPointStatus.objects.create(supply_point=location['case']._id,
                                         status_type=status_type,
                                         status_value=SupplyPointStatusValues.RECEIVED,
                                         status_date=datetime.utcnow())