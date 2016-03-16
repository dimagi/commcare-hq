from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import ARRIVED_HELP, ARRIVED_KNOWN, ARRIVED_DEFAULT


class ArrivedHandler(KeywordHandler):

    def help(self):
        return self.handle()

    def handle(self):
        if not self.args:
            self.respond(ARRIVED_HELP)
            return True

        msdcode = self.args[0]
        try:
            sql_location = SQLLocation.objects.get(domain=self.domain, site_code__iexact=msdcode)
            self.respond(ARRIVED_KNOWN, facility=sql_location.name)
        except SQLLocation.DoesNotExist:
            self.respond(ARRIVED_DEFAULT)
        return True
