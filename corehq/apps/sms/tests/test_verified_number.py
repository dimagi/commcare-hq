from django.test.testcases import TestCase
from corehq.apps.domain.models import Domain
from corehq.apps.sms.tests.util import create_mobile_worker


class TestVerifiedNumber(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = "verified-number-test"

        cls.domain_obj = Domain(name=cls.domain)
        cls.domain_obj.save()

        cls.user1 = create_mobile_worker(cls.domain, 'test-vn', '*****', ['1111'])
        cls.user2 = create_mobile_worker(cls.domain, 'test-vn2', '*****', ['3333', '2222'])
        cls.user3 = create_mobile_worker(cls.domain, 'test-vn3', '*****', ['4444'], save_vn=False)
        cls.user4 = create_mobile_worker(cls.domain, 'test-vn4', '*****', [])

    def test_user_without_number(self):
        self.assertIsNone(self.user4.get_verified_number())

    def test_user_without_verified_number(self):
        self.assertIsNone(self.user3.get_verified_number())

    def test_user_with_one_phone_number(self):
        self.assertEqual(self.user1.get_verified_number().phone_number, '1111')

    def test_user_with_two_phone_numbers(self):
        self.assertEqual(self.user2.get_verified_number().phone_number, '3333')

    @classmethod
    def tearDownClass(cls):
        cls.user1.delete()
        cls.user2.delete()
        cls.user3.delete()
        cls.user4.delete()
        cls.domain_obj.delete()
