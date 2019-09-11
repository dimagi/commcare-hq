from corehq.apps.commtrack.tests.util import bootstrap_domain, make_loc
from corehq.apps.domain.models import Domain
from corehq.apps.sms.api import incoming
from corehq.apps.sms.tests.util import delete_domain_phone_numbers, BaseSMSTest, setup_default_sms_test_backend
from custom.ewsghana.handler import handle
from custom.ewsghana.utils import bootstrap_user
from mock import patch


def get_handle_wrapper(result_dict):
    def inner(*args, **kwargs):
        result_dict['result'] = handle(*args, **kwargs)
        return result_dict['result']

    return inner


class HandlerTest(BaseSMSTest):

    @classmethod
    def setUpClass(cls):
        super(HandlerTest, cls).setUpClass()
        cls.domain = 'ews-handler-test'
        bootstrap_domain(cls.domain)
        cls.create_account_and_subscription(cls.domain)
        cls.domain_obj = Domain.get_by_name(cls.domain)
        cls.loc = make_loc(code="garms", name="Test RMS", type="Regional Medical Store", domain=cls.domain)
        cls.user = bootstrap_user(username='testuser', phone_number='323232', domain=cls.domain,
                                   home_loc=cls.loc)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(HandlerTest, cls).tearDownClass()

    def setUp(self):
        super(HandlerTest, self).setUp()
        self.backend, self.backend_mapping = setup_default_sms_test_backend()

    def tearDown(self):
        delete_domain_phone_numbers(self.domain)
        self.backend.delete()
        self.backend_mapping.delete()
        super(HandlerTest, self).tearDown()

    def _test_pass_through_ews_handler(self, phone_number, message):
        result_dict = {}
        with patch('custom.ewsghana.handler.handle', new=get_handle_wrapper(result_dict)):
            incoming(phone_number, message, 'TEST')
            self.assertFalse(result_dict['result'])

    def test_non_ews_traffic(self):
        # Test that messages from numbers registered to non-ews domains do not get processed by ews
        self._test_pass_through_ews_handler('323232', 'soh dp 40.0')
        self._test_pass_through_ews_handler('323232', 'dp 40.0')
