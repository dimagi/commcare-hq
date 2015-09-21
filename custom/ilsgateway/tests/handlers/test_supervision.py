from custom.ilsgateway.tanzania.reminders import SUPERVISION_CONFIRM_YES, SUPERVISION_CONFIRM_NO
from custom.ilsgateway.tests import ILSTestScript


class TestSupervision(ILSTestScript):

    def test_supervision_yes(self):

        script = """
          5551234 > usimamizi ndio
          5551234 < {0}
        """.format(unicode(SUPERVISION_CONFIRM_YES))
        self.run_script(script)

    def test_supervision_no(self):
        script = """
          5551234 > usimamizi hapana
          5551234 < {0}
        """.format(unicode(SUPERVISION_CONFIRM_NO))
        self.run_script(script)
