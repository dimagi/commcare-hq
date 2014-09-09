from custom.ilsgateway.handlers.keyword import KeywordHandler
from custom.ilsgateway.reminders import LANGUAGE_HELP, LANGUAGE_CONFIRM, LANGUAGE_UNKNOWN, LANGUAGE_CONTACT_REQUIRED
import settings


class LanguageHandler(KeywordHandler):

    def help(self):
        self.respond(LANGUAGE_HELP)

    def handle(self):
        if self.user:
            self.respond(LANGUAGE_CONTACT_REQUIRED)
        language = self.args[0].lower()
        for code, name in settings.LANGUAGES:
            if code.lower() == language or name.lower() == language:
                self.user.language = code
                self.user.save()
                self.respond(LANGUAGE_CONFIRM, language=name)
                return
        self.respond(LANGUAGE_UNKNOWN, language=language)