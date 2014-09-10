from datetime import datetime
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ilsgateway.handlers import get_location
from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.reminders import SOH_HELP_MESSAGE


class SOHHandler(KeywordHandler):

    def handle(self):
        location = get_location(self.domain, self.user, self.args[0])
        if location['location'].location_type == 'FACILITY':
            SupplyPointStatus.objects.create(supply_point=location['case']._id,
                                             status_type=SupplyPointStatusTypes.SOH_FACILITY,
                                             status_value=SupplyPointStatusValues.SUBMITTED,
                                             status_date=datetime.utcnow())

    def help(self):
        self.respond(SOH_HELP_MESSAGE)