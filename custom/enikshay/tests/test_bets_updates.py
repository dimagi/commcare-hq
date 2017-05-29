import json
import uuid
from django.test import TestCase, override_settings, Client
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import create_and_save_a_case, flag_enabled
from custom.enikshay.integrations.bets.views import get_case


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

    def make_request(self, data):
        c = Client()
        c.force_login(self.web_user.get_django_user())
        return c.post("/a/{}/bets/{}".format(self.domain, 'payment_confirmation'),
                      data=json.dumps(data),
                      content_type='application/json')

    def assertResponseStatus(self, response, status_code):
        msg = "expected {} got {}\n{}".format(
            status_code, response.status_code, response.content)
        self.assertEqual(response.status_code, status_code, msg)

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
        res = self.make_request({'response': [{
            'event_type': 'Voucher',
            'id': voucher.case_id,
            # Missing this field
            # 'status': 'Success',
            'amount': 100,
            'payment_date': "2014-11-22 13:23:44.657"
        }]})
        self.assertResponseStatus(res, 400)

    def test_update_voucher_success(self):
        voucher = self.make_voucher()
        res = self.make_request({'response': [{
            'event_type': 'Voucher',
            'id': voucher.case_id,
            'status': 'Success',
            'amount': 100,
            'payment_date': "2014-11-22 13:23:44.657"
        }]})
        self.assertResponseStatus(res, 200)
        # TODO check date parsing
        self.assertDictContainsSubset(
            {'state': 'paid', 'amount_fulfilled': '100'},
            get_case(self.domain, voucher.case_id).case_json,
        )

    def test_update_voucher_failure(self):
        voucher = self.make_voucher()
        res = self.make_request({'response': [{
            'event_type': 'Voucher',
            'id': voucher.case_id,
            'status': 'Failure',
            'remarks': 'The Iron Bank will have its due',
            'amount': 0,
            'payment_date': "2014-11-22 13:23:44.657"
        }]})
        self.assertResponseStatus(res, 200)
        self.assertDictContainsSubset(
            {'state': 'rejected', 'reason_rejected': 'The Iron Bank will have its due'},
            get_case(self.domain, voucher.case_id).case_json,
        )

    def test_update_voucher_unknown_id(self):
        res = self.make_request({'response': [{
            'event_type': 'Voucher',
            'id': "jaqen-hghar",
            'status': 'Success',
            'amount': 100,
            'payment_date': "2014-11-22 13:23:44.657"
        }]})
        self.assertResponseStatus(res, 404)

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
        res = self.make_request({'response': [{
            'event_type': 'Incentive',
            'id': episode.case_id,
            'status': 'Success',
            'bets_parent_event_id': '106',
            'amount': 100,
            'payment_date': "2014-11-22 13:23:44.657"
        }]})
        self.assertResponseStatus(res, 200)
        self.assertDictContainsSubset(
            {
                'tb_incentive_106_status': 'paid',
                'tb_incentive_106_amount': '100',
            },
            get_case(self.domain, episode.case_id).case_json,
        )

    def test_update_incentive_failure(self):
        episode = self.make_episode_case()
        res = self.make_request({'response': [{
            'event_type': 'Incentive',
            'id': episode.case_id,
            'status': 'Failure',
            'remarks': 'We do not sow',
            'bets_parent_event_id': '106',
            'payment_date': "2014-11-22 13:23:44.657"
        }]})
        self.assertResponseStatus(res, 200)
        self.assertDictContainsSubset(
            {
                'tb_incentive_106_status': 'rejected',
                'tb_incentive_106_rejection_reason': 'We do not sow',
            },
            get_case(self.domain, episode.case_id).case_json,
        )

    def test_update_incentive_bad_event(self):
        res = self.make_request({'response': [{
            'event_type': 'Incentive',
            'id': '123',
            'status': 'Success',
            'bets_parent_event_id': '404',
            'amount': 100,
            'payment_date': "2014-11-22 13:23:44.657"
        }]})
        self.assertResponseStatus(res, 400)

    def test_multiple_updates(self):
        episode = self.make_episode_case()
        voucher = self.make_voucher()

        res = self.make_request({'response': [{
            'event_type': 'Incentive',
            'id': episode.case_id,
            'status': 'Failure',
            'remarks': 'We do not sow',
            'bets_parent_event_id': '106',
            'payment_date': "2014-11-22 13:23:44.657"
        }, {
            'event_type': 'Voucher',
            'id': voucher.case_id,
            'status': 'Success',
            'amount': 100,
            'payment_date': "2014-11-22 13:23:44.657"
        }]})
        self.assertResponseStatus(res, 200)

        # check incentive update
        self.assertDictContainsSubset(
            {
                'tb_incentive_106_status': 'rejected',
                'tb_incentive_106_rejection_reason': 'We do not sow',
            },
            get_case(self.domain, episode.case_id).case_json,
        )
        # check voucher update
        self.assertDictContainsSubset(
            {'state': 'paid', 'amount_fulfilled': '100'},
            get_case(self.domain, voucher.case_id).case_json,
        )

    def test_missing_case(self):
        voucher = self.make_voucher()
        res = self.make_request({'response': [{
            'event_type': 'Incentive',
            'id': 'this-is-not-a-real-id',
            'status': 'Success',
            'bets_parent_event_id': '106',
            'amount': 100,
            'payment_date': "2014-11-22 13:23:44.657"
        }, {
            'event_type': 'Voucher',
            'id': voucher.case_id,
            'status': 'Success',
            'amount': 100,
            'payment_date': "2014-11-22 13:23:44.657"
        }]})
        self.assertResponseStatus(res, 404)
