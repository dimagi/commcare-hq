import json
import uuid
from django.test import TestCase, override_settings, RequestFactory
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from custom.enikshay.integrations.bets.views import update_voucher, update_incentive, get_case
from corehq.util.test_utils import create_and_save_a_case, flag_enabled


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
@flag_enabled('ENIKSHAY_API')
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
        self.assertEqual(res.status_code, 400)

    def test_update_voucher_success(self):
        voucher = self.make_voucher()
        res = self.make_request(update_voucher, {
            'voucher_id': voucher.case_id,
            'payment_status': 'success',
            'payment_amount': 100,
        })
        self.assertEqual(res.status_code, 200)
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
        self.assertEqual(res.status_code, 200)
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
        self.assertEqual(res.status_code, 404)

    def make_episode_case(self):
        return create_and_save_a_case(
            self.domain,
            uuid.uuid4().hex,
            case_name='prescription',
            case_properties={'test_confirming_diagnosis': "Old Nan's wisdom",
                             'weight': "15 stone"},
            case_type='episode',
        )

    def test_update_incentive_success(self):
        episode = self.make_episode_case()
        res = self.make_request(update_incentive, {
            'beneficiary_id': episode.case_id,
            'episode_id': episode.case_id,
            'payment_status': 'success',
            'bets_parent_event_id': '106',
            'payment_amount': 100,
        })
        self.assertEqual(res.status_code, 200)
        self.assertDictContainsSubset(
            {
                'tb_incentive_106_status': 'paid',
                'tb_incentive_106_amount': '100',
            },
            get_case(self.domain, episode.case_id).case_json,
        )

    def test_update_incentive_failure(self):
        episode = self.make_episode_case()
        res = self.make_request(update_incentive, {
            'beneficiary_id': episode.case_id,
            'episode_id': episode.case_id,
            'payment_status': 'failure',
            'failure_description': 'We do not sow',
            'bets_parent_event_id': '106',
        })
        self.assertEqual(res.status_code, 200)
        self.assertDictContainsSubset(
            {
                'tb_incentive_106_status': 'rejected',
                'tb_incentive_106_rejection_reason': 'We do not sow',
            },
            get_case(self.domain, episode.case_id).case_json,
        )

    def test_update_incentive_bad_event(self):
        res = self.make_request(update_incentive, {
            'beneficiary_id': '123',
            'episode_id': '123',
            'payment_status': 'success',
            'bets_parent_event_id': '404',
            'payment_amount': 100,
        })
        self.assertEqual(res.status_code, 400)
