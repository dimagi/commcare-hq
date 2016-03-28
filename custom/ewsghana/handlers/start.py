from custom.ewsghana.handlers import START_MESSAGE
from custom.ewsghana.handlers.keyword import KeywordHandler


class StartHandler(KeywordHandler):

    def help(self):
        self.handle()

    def handle(self):
        self.user.user_data['needs_reminders'] = "True"
        self.user.save()
        self.respond(START_MESSAGE)
