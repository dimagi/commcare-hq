from custom.ilsgateway.tanzania.reminders import YES_HELP
from custom.ilsgateway.tanzania.test.utils import ILSTestScript


class TestYes(ILSTestScript):
    
    def test_yes(self):
        script = """
          5551234 > ndio
          5551234 < {0}
        """.format(YES_HELP)
        self.run_script(script)