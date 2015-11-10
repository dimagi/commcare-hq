from custom.ewsghana.handlers import INVALID_MESSAGE, NO_SUPPLY_POINT_MESSAGE
from custom.ewsghana.tests.handlers.utils import EWSScriptTest


class TestDefault(EWSScriptTest):

    def test_default(self):
        a = """
           5551234 > xx 10
           5551234 < xx is not a recognized commodity code. Please contact your DHIO or RHIO for help.
           """
        self.run_script(a)

    def test_default_when_invalid_message_is_sent(self):
        a = """
            5551234 > some random message
            5551234 < {}
        """.format(unicode(INVALID_MESSAGE))
        self.run_script(a)

    def test_default_when_user_has_no_location_association(self):
        a = """
            77777 > dp 10
            77777 < {}
        """.format(unicode(NO_SUPPLY_POINT_MESSAGE))
        self.run_script(a)
