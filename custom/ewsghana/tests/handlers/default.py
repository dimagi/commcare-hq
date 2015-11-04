from custom.ewsghana.handlers import INVALID_MESSAGE
from custom.ewsghana.tests.handlers.utils import EWSScriptTest


class TestDefault(EWSScriptTest):

    def test_default(self):
        a = """
           5551234 > xx 10
           5551234 < xx is not a recognized commodity code. Please contact your DHIO or RHIO for help.
           """
        self.run_script(a)

    def test_default2(self):
        a = """
            77777 > some random message
            77777 < {}
        """.format(unicode(INVALID_MESSAGE))
        self.run_script(a)
