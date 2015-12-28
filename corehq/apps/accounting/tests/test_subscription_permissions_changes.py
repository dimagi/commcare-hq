import os
import json
from corehq.apps.accounting import generator
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, \
    SoftwarePlanEdition, Subscription
from corehq.apps.accounting.tests import BaseAccountingTest
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain



class TestSubscriptionPermissionsChanges(BaseAccountingTest):

    def setUp(self):
        super(TestSubscriptionPermissionsChanges, self).setUp()
        self.domain = Domain(
            name="test-sub-changes",
            is_active=True,
        )
        self.domain.save()

        self.admin_user = generator.arbitrary_web_user()
        self.admin_user.add_domain_membership(self.domain.name, is_admin=True)
        self.admin_user.save()

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.domain.name, created_by=self.admin_user.username)[0]
        self.advanced_plan = DefaultProductPlan.get_default_plan_by_domain(
            self.domain.name, edition=SoftwarePlanEdition.ADVANCED)

    def test_app_icon_permissions(self):
        LOGO_HOME = u'hq_logo_android_home'
        LOGO_LOGIN = u'hq_logo_android_login'

        advanced_sub = Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_user.username
        )
        with open(os.path.join(os.path.dirname(__file__), 'data', 'app-commcare-icon-standard.json')) as f:
            standard_source = json.load(f)
        with open(os.path.join(os.path.dirname(__file__), 'data', 'app-commcare-icon-build.json')) as f:
            build_source = json.load(f)

        app_standard = Application.wrap(standard_source)
        app_standard.save()
        self.assertEqual(self.domain.name, app_standard.domain)

        app_build = Application.wrap(build_source)
        app_build.save()
        self.assertEqual(self.domain.name, app_build.domain)

        self.assertTrue(LOGO_HOME in app_standard.logo_refs.keys())
        self.assertTrue(LOGO_LOGIN in app_standard.logo_refs.keys())
        self.assertTrue(LOGO_HOME in app_build.logo_refs.keys())
        self.assertTrue(LOGO_LOGIN in app_build.logo_refs.keys())

        advanced_sub.cancel_subscription(web_user=self.admin_user.username)

        app_standard = Application.get(app_standard._id)
        app_build = Application.get(app_build._id)

        self.assertFalse(LOGO_HOME in app_standard.logo_refs.keys())
        self.assertFalse(LOGO_LOGIN in app_standard.logo_refs.keys())
        self.assertFalse(LOGO_HOME in app_build.logo_refs.keys())
        self.assertFalse(LOGO_LOGIN in app_build.logo_refs.keys())

        Subscription.new_domain_subscription(
            self.account, self.domain.name, self.advanced_plan,
            web_user=self.admin_user.username
        )

        app_standard = Application.get(app_standard._id)
        app_build = Application.get(app_build._id)

        self.assertTrue(LOGO_HOME in app_standard.logo_refs.keys())
        self.assertTrue(LOGO_LOGIN in app_standard.logo_refs.keys())
        self.assertTrue(LOGO_HOME in app_build.logo_refs.keys())
        self.assertTrue(LOGO_LOGIN in app_build.logo_refs.keys())

    def tearDown(self):
        self.domain.delete()
        self.admin_user.delete()
        generator.delete_all_subscriptions()
        generator.delete_all_accounts()
        super(TestSubscriptionPermissionsChanges, self).tearDown()
