from datetime import datetime
from custom.ilsgateway.handlers import get_location
from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues


class NotDeliveredHandler(KeywordHandler):

    def help(self):
        self.handle()

    def handle(self):
        location = get_location(self.domain, self.user, None)
        status_type = None
        if location['location'].location_type == 'FACILITY':
            status_type = SupplyPointStatusTypes.DELIVERY_FACILITY
        elif location['location'].location_type == 'DISTRICT':
            status_type = SupplyPointStatusTypes.DELIVERY_DISTRICT

        SupplyPointStatus.objects.create(supply_point=location['case']._id,
                                         status_type=status_type,
                                         status_value=SupplyPointStatusValues.NOT_RECEIVED,
                                         status_date=datetime.utcnow())