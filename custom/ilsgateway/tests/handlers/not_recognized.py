from custom.ilsgateway.tanzania.reminders import CONTACT_SUPERVISOR
from custom.ilsgateway.tests import ILSTestScript


class ILSNotRecognized(ILSTestScript):

    def test_not_recognized_keyword(self):
        self.run_script(
            """
                5551234 > asdsdasdassd
                5551234 < {0}
            """.format(unicode(CONTACT_SUPERVISOR))
        )
