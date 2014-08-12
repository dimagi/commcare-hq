from corehq.apps.commtrack.util import get_supply_point
from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.reminders import ARRIVED_HELP, ARRIVED_KNOWN, ARRIVED_DEFAULT


class ArrivedHandler(KeywordHandler):
    
    def help(self):
        self.handle()
    
    def handle(self):
        if not self.args:
            self.respond(ARRIVED_HELP)
            return

        msdcode = self.args[0]
        location = get_supply_point(self.domain, site_code=msdcode)

        if location:
            self.respond(ARRIVED_KNOWN, facility=location['case'].name)
        else:
            self.respond(ARRIVED_DEFAULT)
