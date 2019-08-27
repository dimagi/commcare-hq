from custom.ewsghana.handlers import DEACTIVATE_REMINDERS, REACTIVATE_REMINDERS, START_MESSAGE, STOP_MESSAGE
from custom.ewsghana.handlers.keyword import KeywordHandler
from custom.ewsghana.utils import user_needs_reminders


class ReminderOnOffHandler(KeywordHandler):

    def help(self):
        if user_needs_reminders(self.user):
            self.respond(DEACTIVATE_REMINDERS)
        else:
            self.respond(REACTIVATE_REMINDERS)

    def handle(self):
        action = self.args[0].lower()
        if action == 'on':
            self.user.user_data['needs_reminders'] = "True"
            self.user.save()
            self.respond(START_MESSAGE)
        elif action == 'off':
            self.user.user_data['needs_reminders'] = "False"
            self.user.save()
            self.respond(STOP_MESSAGE)
        else:
            self.help()
