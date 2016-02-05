from custom.ewsghana.handlers import STOP_MESSAGE
from custom.ewsghana.handlers.keyword import KeywordHandler


class StopHandler(KeywordHandler):

    def help(self):
        self.handle()

    def handle(self):
        self.user.user_data['needs_reminders'] = "False"
        self.user.save()
        self.respond(STOP_MESSAGE)
