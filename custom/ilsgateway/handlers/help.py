from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.reminders import HELP_REGISTERED, HELP_UNREGISTERED


class HelpHandler(KeywordHandler):

    def help(self):
        if self.user:
            self.respond(HELP_REGISTERED)
        else:
            self.respond(HELP_UNREGISTERED)
