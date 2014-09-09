from datetime import datetime
from custom.ilsgateway.handlers import get_location
from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues


class NotSubmittedHandler(KeywordHandler):

    def help(self):
        self.handle()

    def handle(self):
        location = get_location(self.domain, self.user, None)
        SupplyPointStatus.objects.create(supply_point=location['case']._id,
                                         status_type=SupplyPointStatusTypes.R_AND_R_FACILITY,
                                         status_value=SupplyPointStatusValues.NOT_SUBMITTED,
                                         status_date=datetime.utcnow())