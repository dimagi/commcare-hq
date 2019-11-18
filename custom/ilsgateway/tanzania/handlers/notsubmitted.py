from datetime import datetime

from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import NOT_SUBMITTED_CONFIRM


class NotSubmittedHandler(KeywordHandler):

    def help(self):
        return self.handle()

    def handle(self):
        location = self.user.location
        SupplyPointStatus.objects.create(location_id=location.get_id,
                                         status_type=SupplyPointStatusTypes.R_AND_R_FACILITY,
                                         status_value=SupplyPointStatusValues.NOT_SUBMITTED,
                                         status_date=datetime.utcnow())
        self.respond(NOT_SUBMITTED_CONFIRM)
        return True
