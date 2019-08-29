from custom.ewsghana.tests.handlers.utils import EWSScriptTest


class ReceiptsTest(EWSScriptTest):

    def test_receipts(self):
        a = """
           5551234 > rec jd 10
           5551234 < Thank you, you reported receipts for jd.
           5551234 > rec jd 10 mc 20
           5551234 < Thank you, you reported receipts for jd mc.
        """
        self.run_script(a)
