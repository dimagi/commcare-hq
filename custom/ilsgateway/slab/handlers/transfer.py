from __future__ import absolute_import
import re

from datetime import datetime

from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.slab.messages import TRANS_HELP
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import SOH_CONFIRM


class TransferHandler(KeywordHandler):

    def help(self):
        self.respond(TRANS_HELP)
        return True

    def handle(self):
        sub_command = self.args[0].strip().lower()
        now = datetime.utcnow()
        if re.match("hap", sub_command) or re.match("no", sub_command):
            SupplyPointStatus.objects.create(
                status_type=SupplyPointStatusTypes.TRANS_FACILITY,
                status_value=SupplyPointStatusValues.NOT_SUBMITTED,
                location_id=self.location_id,
                status_date=now
            )
        elif re.match("ndi", sub_command) or re.match("yes", sub_command):
            SupplyPointStatus.objects.create(
                status_type=SupplyPointStatusTypes.TRANS_FACILITY,
                status_value=SupplyPointStatusValues.SUBMITTED,
                location_id=self.location_id,
                status_date=now
            )

        else:
            self.help()
            return True
        self.respond(SOH_CONFIRM)
        return True
