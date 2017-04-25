import json
import uuid
from django.test import TestCase, override_settings, RequestFactory
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from custom.enikshay.integrations.bets.views import update_voucher, update_incentive, get_case
from corehq.util.test_utils import create_and_save_a_case


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestBetsUpdates(TestCase):
    domain = 'enikshay-bets-updates'

    @classmethod
    def setUpClass(cls):
        super(TestBetsUpdates, cls).setUpClass()
        cls.domain_obj = Domain(name=cls.domain, is_active=True)
        cls.domain_obj.save()
        cls.web_user = WebUser.create(cls.domain, 'blah', 'password')

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        cls.web_user.delete()
        super(TestBetsUpdates, cls).tearDownClass()

    def make_request(self, view, data):
        factory = RequestFactory()
        request = factory.post("/a/enikshay/bets/{}".format(view.__name__),
                               data=json.dumps(data),
                               content_type='application/json')
        request.user = self.web_user.get_django_user()
        return view(request, self.domain)

    def make_voucher(self):
        return create_and_save_a_case(
            self.domain,
            uuid.uuid4().hex,
            case_name='prescription',
            case_properties={'amount_initial': '105',
                             'state': 'approved'},
            case_type='voucher',
        )

    def test_invalid_request(self):
        voucher = self.make_voucher()
        res = self.make_request(update_voucher, {
            'voucher_id': voucher.case_id,
            # Missing this field
            # 'payment_status': 'success',
            'payment_amount': 100,
        })
        self.assertEqual(res.status_code, 400, res.content)

    def test_update_voucher_success(self):
        voucher = self.make_voucher()
        res = self.make_request(update_voucher, {
            'voucher_id': voucher.case_id,
            'payment_status': 'success',
            'payment_amount': 100,
        })
        self.assertEqual(res.status_code, 200, res.content)
        self.assertDictContainsSubset(
            {'state': 'paid', 'amount_fulfilled': '100'},
            get_case(self.domain, voucher.case_id).case_json,
        )

    def test_update_voucher_failure(self):
        voucher = self.make_voucher()
        res = self.make_request(update_voucher, {
            'voucher_id': voucher.case_id,
            'payment_status': 'failure',
            'failure_description': 'The Iron Bank will have its due',
            'payment_amount': 0,
        })
        self.assertEqual(res.status_code, 200, res.content)
        self.assertDictContainsSubset(
            {'state': 'rejected', 'reason_rejected': 'The Iron Bank will have its due'},
            get_case(self.domain, voucher.case_id).case_json,
        )

    def test_update_voucher_unknown_id(self):
        res = self.make_request(update_voucher, {
            'voucher_id': "jaqen-hghar",
            'payment_status': 'success',
            'payment_amount': 100,
        })
        self.assertEqual(res.status_code, 404, res.content)
