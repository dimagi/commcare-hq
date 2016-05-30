from corehq.util.translation import localize
from custom.ilsgateway.tanzania.reminders import HELP_REGISTERED
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class TestHelp(ILSTestScript):

    def test_help_registered(self):
        with localize('sw'):
            response = unicode(HELP_REGISTERED)

        script = """
          5551234 > msaada
          5551234 < %(help_registered)s
        """ % {'help_registered': response}
        self.run_script(script)

        script = """
          5555678 > help
          5555678 < %(help_registered)s
        """ % {'help_registered': response}
        self.run_script(script)
