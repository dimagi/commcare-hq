from custom.ewsghana.tests import EWSScriptTest


class TestDefault(EWSScriptTest):

    def test_default(self):
        a = """
           5551234 > xx 10
           5551234 < xx is not a recognized commodity code. Please contact your DHIO or RHIO for help.
           """
        self.run_script(a)
