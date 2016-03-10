from django.utils import translation

from corehq.util.translation import localize
from custom.ilsgateway.tanzania.reminders import LANGUAGE_CONFIRM, LANGUAGE_UNKNOWN, HELP_REGISTERED
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class ILSLanguageTest(ILSTestScript):

    def _verify_language(self, language, phone_number):
        previous_language = translation.get_language()
        translation.activate(language)
        expected = unicode(HELP_REGISTERED)
        translation.activate(previous_language)
        script = """
          %(phone)s > help
          %(phone)s < %(help_registered)s
        """ % {'phone': phone_number, 'help_registered': expected}
        self.run_script(script)

    def test_language_english(self):
        with localize('en'):
            response = unicode(LANGUAGE_CONFIRM)
        script = """
            5551234 > language en
            5551234 < %(language_confirm)s
            """ % {'language_confirm': response % {"language": "English"}}
        self.run_script(script)
        self._verify_language('en', '5551234')

    def test_language_swahili(self):
        with localize('sw'):
            response = unicode(LANGUAGE_CONFIRM)
        script = """
            5551234 > lugha sw
            5551234 < %(language_confirm)s
            """ % {'language_confirm': response % {"language": "Swahili"}}
        self.run_script(script)
        self._verify_language('sw', '5551234')

    def test_language_unknown(self):
        with localize('sw'):
            response = unicode(LANGUAGE_UNKNOWN)
        script = """
            5551234 > language de
            5551234 < %(language_unknown)s
            """ % {'language_unknown': response % {"language": "de"}}
        self.run_script(script)
