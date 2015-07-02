from datetime import datetime
from corehq.apps.locations.models import SQLLocation

from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import SOH_HELP_MESSAGE


class SOHHandler(KeywordHandler):

    def handle(self):
        location = self.user.location
        if not location:
            try:
                location_id = SQLLocation.objects.get(domain=self.domain, site_code=self.args[0]).location_id
            except SQLLocation.DoesNotExist:
                return False
        else:
            location_id = location.get_id
        if location.location_type == 'FACILITY':
            SupplyPointStatus.objects.create(location_id=location_id,
                                             status_type=SupplyPointStatusTypes.SOH_FACILITY,
                                             status_value=SupplyPointStatusValues.SUBMITTED,
                                             status_date=datetime.utcnow())
        return False

    def help(self):
        self.respond(SOH_HELP_MESSAGE)
        return True
