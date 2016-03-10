from corehq.util.translation import localize
from custom.ilsgateway.tanzania.reminders import CONTACT_SUPERVISOR
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class ILSNotRecognized(ILSTestScript):

    def test_not_recognized_keyword(self):
        with localize('sw'):
            response = unicode(CONTACT_SUPERVISOR)
        self.run_script(
            """
                5551234 > asdsdasdassd
                5551234 < {0}
            """.format(response)
        )
