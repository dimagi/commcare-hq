from django.utils import translation

from custom.ilsgateway.tanzania.reminders import HELP_REGISTERED
from custom.ilsgateway.tests import ILSTestScript


class TestHelp(ILSTestScript):

    def test_help_registered(self):
        translation.activate('sw')

        script = """
          5551234 > msaada
          5551234 < %(help_registered)s
        """ % {'help_registered': unicode(HELP_REGISTERED)}
        self.run_script(script)

        script = """
          5555678 > help
          5555678 < %(help_registered)s
        """ % {'help_registered': unicode(HELP_REGISTERED)}
        self.run_script(script)
