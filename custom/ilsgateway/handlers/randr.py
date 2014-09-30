from datetime import datetime
from corehq.apps.commtrack.models import CommTrackUser
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.users.models import CouchUser

from custom.ilsgateway.handlers import get_location
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues, \
    DeliveryGroupReport
from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.reminders import SUBMITTED_NOTIFICATION_MSD


class RandrHandler(KeywordHandler):

    def handle(self):
        self._handle()

    def help(self):
        self._handle(help=True)

    def _send_submission_alert_to_msd(self, params):
        users = filter(lambda u: u.user_data.get('role', None) == 'MSD', CommTrackUser.by_domain(self.domain))
        for user in users:
            if user.get_verified_number():
                send_sms_to_verified_number(user.get_verified_number(), SUBMITTED_NOTIFICATION_MSD % params)

    def _handle(self, help=False):
        location = get_location(self.domain, self.user, None)
        status_type = None
        if location['location'].location_type == 'FACILITY':
            status_type = SupplyPointStatusTypes.R_AND_R_FACILITY
        elif location['location'].location_type == 'DISTRICT':
            if help:
                quantities = [0, 0, 0]
            else:
                quantities = [self.args[1], self.args[3], self.args[5]]
                DeliveryGroupReport.objects.create(
                    supply_point=location['case']._id,
                    quantity=quantities[0],
                    message=self.msg._id,
                    delivery_group="A")
                DeliveryGroupReport.objects.create(
                    supply_point=location['case']._id,
                    quantity=quantities[1],
                    message=self.msg._id,
                    delivery_group="B")
                DeliveryGroupReport.objects.create(
                    supply_point=location['case']._id,
                    quantity=quantities[2],
                    message=self.msg._id,
                    delivery_group="C")
            status_type = SupplyPointStatusTypes.R_AND_R_DISTRICT
            params = {
                'district_name': location['case'].name,
                'group_a': quantities[0],
                'group_b': quantities[1],
                'group_c': quantities[2]
            }
            self._send_submission_alert_to_msd(params)
        SupplyPointStatus.objects.create(supply_point=location['case']._id,
                                         status_type=status_type,
                                         status_value=SupplyPointStatusValues.SUBMITTED,
                                         status_date=datetime.utcnow())