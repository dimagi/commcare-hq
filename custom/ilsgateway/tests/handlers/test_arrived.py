from custom.ilsgateway.tanzania.reminders import ARRIVED_HELP, ARRIVED_DEFAULT, ARRIVED_KNOWN
from custom.ilsgateway.tests import ILSTestScript


class ILSArrivedTest(ILSTestScript):

    def setUp(self):
        super(ILSArrivedTest, self).setUp()

    def test_arrived_help(self):
        msg = """
           5551234 > arrived
           5551234 < {0}
        """.format(unicode(ARRIVED_HELP))
        self.run_script(msg)

    def test_arrived_unknown_code(self):
        msg = """
           5551234 > arrived NOTACODEINTHESYSTEM
           5551234 < {0}
        """.format(unicode(ARRIVED_DEFAULT))
        self.run_script(msg)

    def test_arrived_known_code(self):
        msg = """
           5551234 > arrived loc1
           5551234 < {0}
        """.format(unicode(ARRIVED_KNOWN) % {'facility': self.loc1.name})
        self.run_script(msg)

    def test_arrived_with_time(self):
        msg = """
            5551234 > arrived loc1 10:00
            5551234 < {0}
        """.format(unicode(ARRIVED_KNOWN % {'facility': self.loc1.name}))
        self.run_script(msg)
