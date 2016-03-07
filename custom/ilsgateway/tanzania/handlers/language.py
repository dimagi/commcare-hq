from django.conf import settings

from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import LANGUAGE_HELP, LANGUAGE_CONFIRM, LANGUAGE_UNKNOWN, LANGUAGE_CONTACT_REQUIRED


class LanguageHandler(KeywordHandler):

    def help(self):
        self.respond(LANGUAGE_HELP)
        return True

    def handle(self):
        language = self.args[0].lower()
        languages = {
            'sw': 'Swahili',
            'en': 'English'
        }
        language_name = languages.get(language)
        if language_name:
            self.respond(LANGUAGE_CONFIRM, language=language_name)
        else:
            self.respond(LANGUAGE_UNKNOWN, language=language)
        return True
