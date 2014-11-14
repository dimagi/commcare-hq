from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.models import CommConnectCase
from custom.ewsghana.reminders import REGISTER_MESSAGE, NO_SUPPLY_POINT_MESSAGE, REQ_SUBMITTED, \
    REQ_NOT_SUBMITTED
from custom.ilsgateway.models import RequisitionReport
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler


class RequisitionHandler(KeywordHandler):
    keyword = "yes|no|y|n"

    def help(self):
        return self.handle()

    def handle(self):
        text = self.msg.text.strip().lower()
        if not self.user.domain == 'ilsgateway':
            self.respond(REGISTER_MESSAGE)
            return
        if not self.user.location_id is None:
            self.respond(NO_SUPPLY_POINT_MESSAGE)
            return
        sql_loc = SQLLocation.objects.get(location_id=self.user.location_id)
        if text[0] == 'y':
            submitted = True
            response = REQ_SUBMITTED
        else:
            submitted = False
            response = REQ_NOT_SUBMITTED

        r = RequisitionReport(location_id=sql_loc.supply_point_id, submitted=submitted)
        r.save()

        self.respond(response)
