from __future__ import absolute_import
from datetime import datetime

from corehq.apps.users.models import CommCareUser
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.util.translation import localize
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues, \
    DeliveryGroupReport
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import SUBMITTED_NOTIFICATION_MSD, SUBMITTED_CONFIRM, \
    SUBMITTED_REMINDER_DISTRICT, SUBMITTED_INVALID_QUANTITY
from custom.ilsgateway.utils import send_translated_message


class RandrHandler(KeywordHandler):

    def handle(self):
        return self._handle()

    def help(self):
        return self._handle(help=True)

    def _send_submission_alert_to_msd(self, params):
        users = [u for u in CommCareUser.by_domain(self.domain) if u.user_data.get('role', None) == 'MSD']
        for user in users:
            send_translated_message(user, SUBMITTED_NOTIFICATION_MSD, **params)

    def _handle(self, help=False):
        location = self.user.location
        status_type = None
        if location.location_type_name == 'FACILITY':
            status_type = SupplyPointStatusTypes.R_AND_R_FACILITY
            self.respond(SUBMITTED_CONFIRM, sp_name=location.name, contact_name=self.user.name)
        elif location.location_type_name == 'DISTRICT':
            if help:
                quantities = [0, 0, 0]
                self.respond(SUBMITTED_REMINDER_DISTRICT)
            else:
                quantities = [self.args[1], self.args[3], self.args[5]]

                for quantity in quantities:
                    try:
                        int(quantity)
                    except ValueError:
                        self.respond(SUBMITTED_INVALID_QUANTITY % {'number': quantity})
                        return True

                DeliveryGroupReport.objects.create(
                    location_id=location.get_id,
                    quantity=quantities[0],
                    message=self.msg.couch_id,
                    delivery_group="A"
                )
                DeliveryGroupReport.objects.create(
                    location_id=location.get_id,
                    quantity=quantities[1],
                    message=self.msg.couch_id,
                    delivery_group="B"
                )
                DeliveryGroupReport.objects.create(
                    location_id=location.get_id,
                    quantity=quantities[2],
                    message=self.msg.couch_id,
                    delivery_group="C"
                )
                self.respond(
                    SUBMITTED_CONFIRM,
                    sp_name=location.name,
                    contact_name=self.user.first_name + " " + self.user.last_name
                )
            status_type = SupplyPointStatusTypes.R_AND_R_DISTRICT
            params = {
                'district_name': location.name,
                'group_a': quantities[0],
                'group_b': quantities[1],
                'group_c': quantities[2]
            }
            self._send_submission_alert_to_msd(params)
        SupplyPointStatus.objects.create(location_id=location.get_id,
                                         status_type=status_type,
                                         status_value=SupplyPointStatusValues.SUBMITTED,
                                         status_date=datetime.utcnow())
        return True
