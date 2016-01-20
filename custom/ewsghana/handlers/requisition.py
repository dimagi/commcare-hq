from corehq.apps.locations.models import SQLLocation
from custom.ewsghana.handlers.keyword import KeywordHandler
from custom.ewsghana.reminders import NO_SUPPLY_POINT_MESSAGE, REQ_SUBMITTED, \
    REQ_NOT_SUBMITTED
from custom.ilsgateway.models import RequisitionReport


class RequisitionHandler(KeywordHandler):
    keyword = "yes|no|y|n"

    def help(self):
        return self.handle()

    def handle(self):
        text = self.msg.text.strip().lower()
        if self.user.location_id is None:
            self.respond(NO_SUPPLY_POINT_MESSAGE)
            return True
        sql_loc = SQLLocation.objects.get(location_id=self.user.location_id)
        if text[0] in ['y', 'yes']:
            submitted = True
            response = REQ_SUBMITTED
        else:
            submitted = False
            response = REQ_NOT_SUBMITTED
        if sql_loc.supply_point_id:
            r = RequisitionReport(location_id=sql_loc.supply_point_id, submitted=submitted)
            r.save()

        self.respond(response)
        return True
