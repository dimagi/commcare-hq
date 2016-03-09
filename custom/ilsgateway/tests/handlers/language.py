from django.utils import translation

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
        translation.activate('en')
        script = """
            5551234 > language en
            5551234 < %(language_confirm)s
            """ % {'language_confirm': unicode(LANGUAGE_CONFIRM) % {"language": "English"}}
        self.run_script(script)
        self._verify_language('en', '5551234')

    def test_language_swahili(self):
        translation.activate('sw')
        script = """
            5551234 > lugha sw
            5551234 < %(language_confirm)s
            """ % {'language_confirm': unicode(LANGUAGE_CONFIRM) % {"language": "Swahili"}}
        self.run_script(script)
        self._verify_language('sw', '5551234')

    def test_language_unknown(self):
        translation.activate('sw')
        script = """
            5551234 > language de
            5551234 < %(language_unknown)s
            """ % {'language_unknown': unicode(LANGUAGE_UNKNOWN) % {"language": "de"}}
        self.run_script(script)
