from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import STOP_CONFIRM


class StopHandler(KeywordHandler):

    def help(self):
        return self.handle()

    def handle(self):
        self.user.is_active = False
        self.user.save()
        self.respond(STOP_CONFIRM)
        return True
