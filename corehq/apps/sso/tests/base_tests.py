from django.test import TestCase

from django_prbac.models import Role

from corehq.apps.accounting.tests import generator


class BaseSSOTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Role.get_cache().clear()

        billing_contact = generator.create_arbitrary_web_user_name()
        dimagi_user = generator.create_arbitrary_web_user_name(
            is_dimagi=True)
        cls.account = generator.billing_account(
            dimagi_user, billing_contact
        )
        cls.domain = generator.arbitrary_domain()
        cls.account.is_customer_billing_account = True
        cls.account.save()

    @classmethod
    def tearDownClass(cls):
        for user in cls.domain.all_users():
            user.delete(deleted_by=None)
        cls.domain.delete()
        cls.account.delete()
        super().tearDownClass()
