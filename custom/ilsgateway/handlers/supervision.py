from datetime import datetime
import re
from custom.ilsgateway.handlers import get_location
from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatusValues, SupplyPointStatus, SupplyPointStatusTypes
from custom.ilsgateway.reminders import SUPERVISION_HELP


class SupervisionHandler(KeywordHandler):
    
    def help(self):
        self.respond(SUPERVISION_HELP)

    def handle(self):
        subcommand = self.args[0].strip().lower()
        location = get_location(self.domain, self.user, None)
        if not location:
            return
        if re.match("hap", subcommand) or re.match("no", subcommand):
            status_value = SupplyPointStatusValues.NOT_RECEIVED
        elif re.match("ndi", subcommand) or re.match("yes", subcommand):
            status_value = SupplyPointStatusValues.RECEIVED
        else:
            self.help()
            return

        SupplyPointStatus.objects.create(status_type=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                                             status_value=status_value,
                                             supply_point=location['case']._id,
                                             status_date=datetime.utcnow())
