from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import YES_HELP


class YesHandler(KeywordHandler):

    def help(self):
        self.handle()

    def handle(self):
        self.respond(YES_HELP)