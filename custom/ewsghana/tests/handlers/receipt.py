from corehq.apps.commtrack.tests.util import bootstrap_user, make_loc, TEST_BACKEND
from corehq.apps.products.models import Product
from corehq.apps.sms.backend import test
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.models import EWSGhanaConfig
from custom.ewsghana.tests.test_script import TestScript
from custom.ewsghana.utils import prepare_domain

TEST_DOMAIN = 'ewsghana-receipts-test'


class ReceiptsTest(TestScript):

    def setUp(self):
        self.domain = prepare_domain(TEST_DOMAIN)
        self.loc = make_loc(code="garms", name="Test RMS", type="Regional Medical Store", domain=self.domain.name)
        self.backend = test.bootstrap(TEST_BACKEND, to_console=True)
        self.user = bootstrap_user(self, username='stella', domain=self.domain.name, home_loc='garms')
        p = Product(domain=self.domain.name, name='Jadelle', code='jd', unit='each')
        p.save()
        p2 = Product(domain=self.domain.name, name='Mc', code='mc', unit='each')
        p2.save()


    def test_receipts(self):
        a = """
           5551234 > jd 10.0
           5551234 < Thank you, you reported receipts for jd.
           5551234 > jd 10.0 mc 20.0
           5551234 < Thank you, you reported receipts for jd mc.
        """
        self.run_script(a)