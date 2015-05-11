from datetime import datetime
import re

from custom.ilsgateway.tanzania.handlers import get_location
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.models import SupplyPointStatusValues, SupplyPointStatus, SupplyPointStatusTypes
from custom.ilsgateway.tanzania.reminders import SUPERVISION_HELP, SUPERVISION_CONFIRM_NO, SUPERVISION_CONFIRM_YES


class SupervisionHandler(KeywordHandler):
    
    def help(self):
        self.respond(SUPERVISION_HELP)

    def handle(self):
        subcommand = self.args[0].strip().lower()
        location = self.user.location
        if not location:
            return
        if re.match("hap", subcommand) or re.match("no", subcommand):
            status_value = SupplyPointStatusValues.NOT_RECEIVED
            self.respond(SUPERVISION_CONFIRM_NO)
        elif re.match("ndi", subcommand) or re.match("yes", subcommand):
            status_value = SupplyPointStatusValues.RECEIVED
            self.respond(SUPERVISION_CONFIRM_YES)
        else:
            self.help()
            return

        SupplyPointStatus.objects.create(status_type=SupplyPointStatusTypes.SUPERVISION_FACILITY,
                                         status_value=status_value,
                                         supply_point=location.get_id,
                                         status_date=datetime.utcnow())
