from __future__ import absolute_import
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import YES_HELP


class YesHandler(KeywordHandler):

    def help(self):
        return self.handle()

    def handle(self):
        self.respond(YES_HELP)
        return True
