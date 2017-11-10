from __future__ import absolute_import
from datetime import datetime

from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import NOT_DELIVERED_CONFIRM


class NotDeliveredHandler(KeywordHandler):

    def help(self):
        return self.handle()

    def handle(self):
        location = self.user.location
        status_type = None
        if location.location_type_name == 'FACILITY':
            status_type = SupplyPointStatusTypes.DELIVERY_FACILITY
        elif location.location_type_name == 'DISTRICT':
            status_type = SupplyPointStatusTypes.DELIVERY_DISTRICT

        self.respond(NOT_DELIVERED_CONFIRM)

        SupplyPointStatus.objects.create(location_id=location.get_id,
                                         status_type=status_type,
                                         status_value=SupplyPointStatusValues.NOT_RECEIVED,
                                         status_date=datetime.utcnow())
        return True
