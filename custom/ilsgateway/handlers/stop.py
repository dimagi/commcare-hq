from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.reminders import STOP_CONFIRM


class StopHandler(KeywordHandler):

    def help(self):
        self.handle()

    def handle(self):
        self.user.is_active = False
        self.user.save()
        self.respond(STOP_CONFIRM)