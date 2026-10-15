"""Shared setup for tests covering the wire prepayment invoice workflow."""

import datetime

from django.test import Client, TestCase

from django_prbac.models import Role

from corehq.apps.accounting import utils
from corehq.apps.accounting.models import SoftwarePlanEdition, SubscriptionType
from corehq.apps.accounting.tests import generator
from corehq.apps.users.models import WebUser


class WirePrepaymentTestCase(TestCase):
    """A domain on an active paid subscription, with a logged-in billing admin"""

    plan_edition = SoftwarePlanEdition.ADVANCED
    username = 'prepay-admin@example.com'
    password = 'testpwd'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Role.get_cache().clear()
        generator.bootstrap_test_software_plan_versions()
        generator.init_default_currency()
        cls.addClassCleanup(utils.clear_plan_version_cache)

        cls.domain_obj = generator.arbitrary_domain()
        cls.addClassCleanup(cls.domain_obj.delete)

        cls.web_user = WebUser.create(
            cls.domain_obj.name,
            cls.username,
            cls.password,
            None,
            None,
            is_admin=True,
        )
        cls.addClassCleanup(
            cls.web_user.delete, cls.domain_obj.name, deleted_by=None
        )

        cls.account = generator.billing_account(cls.username, cls.username)
        cls.subscription = generator.generate_domain_subscription(
            cls.account,
            cls.domain_obj,
            date_start=datetime.date.today() - datetime.timedelta(days=30),
            date_end=None,
            plan_version=generator.subscribable_plan_version(cls.plan_edition),
            service_type=SubscriptionType.PRODUCT,
            is_active=True,
        )

        # named to avoid shadowing the fresh, anonymous self.client that
        # SimpleTestCase builds for each test
        cls.admin_client = Client()
        cls.admin_client.login(username=cls.username, password=cls.password)
