import json
import os

from django_prbac.models import Grant, Role

from corehq import privileges
from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    ProBonoStatus,
    SoftwarePlan,
    SoftwarePlanEdition,
    SoftwarePlanVersion,
    SoftwarePlanVisibility,
    Subscription,
    SubscriptionType,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
    ReportMeta,
    get_datasource_config,
)


class TestSubscriptionPermissionsChanges(BaseAccountingTest):

    def setUp(self):
        super(TestSubscriptionPermissionsChanges, self).setUp()
        self.project = Domain(
            name="test-sub-changes",
            is_active=True,
        )
        self.project.save()

        self.admin_username = generator.create_arbitrary_web_user_name()

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.project.name, created_by=self.admin_username)[0]
        self.advanced_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        self._init_pro_with_rb_plan_and_version()

    def _init_pro_with_rb_plan_and_version(self):
        plan = SoftwarePlan(
            name="Pro_with_30_RB_reports",
            description="Pro + 30 report builder reports",
            edition=SoftwarePlanEdition.PRO,
            visibility=SoftwarePlanVisibility.INTERNAL,
        )
        plan.save()

        role = Role.objects.create(
            slug="pro_with_rb_30_role",
            name="Pro + 30 rb reports",
        )
        for privilege in [privileges.REPORT_BUILDER_30]:  # Doesn't actually include the pro roles...
            privilege = Role.objects.get(slug=privilege)
            Grant.objects.create(
                from_role=role,
                to_role=privilege,
            )
        self.pro_rb_version = SoftwarePlanVersion(
            plan=plan,
            role=role
        )
        self.pro_rb_version.product_rate = DefaultProductPlan.get_default_plan_version(
            SoftwarePlanEdition.PRO
        ).product_rate
        self.pro_rb_version.save()

    def _subscribe_to_advanced(self):
        return Subscription.new_domain_subscription(
            self.account, self.project.name, self.advanced_plan,
            web_user=self.admin_username
        )

    def _subscribe_to_pro_with_rb(self):
        subscription = Subscription.get_active_subscription_by_domain(self.project.name)

        new_subscription = subscription.change_plan(
            self.pro_rb_version,
            date_end=None,
            web_user=self.admin_username,
            service_type=SubscriptionType.IMPLEMENTATION,
            pro_bono_status=ProBonoStatus.NO,
            internal_change=True,
        )
        return new_subscription

    def test_app_icon_permissions(self):
        LOGO_HOME = 'hq_logo_android_home'
        LOGO_LOGIN = 'hq_logo_android_login'

        advanced_sub = self._subscribe_to_advanced()

        with open(os.path.join(os.path.dirname(__file__), 'data', 'app-commcare-icon-standard.json')) as f:
            standard_source = json.load(f)
        with open(os.path.join(os.path.dirname(__file__), 'data', 'app-commcare-icon-build.json')) as f:
            build_source = json.load(f)

        app_standard = Application.wrap(standard_source)
        app_standard.save()
        self.assertEqual(self.project.name, app_standard.domain)

        app_build = Application.wrap(build_source)
        app_build.save()
        self.assertEqual(self.project.name, app_build.domain)

        self.assertTrue(LOGO_HOME in app_standard.logo_refs)
        self.assertTrue(LOGO_LOGIN in app_standard.logo_refs)
        self.assertTrue(LOGO_HOME in app_build.logo_refs)
        self.assertTrue(LOGO_LOGIN in app_build.logo_refs)

        community_sub = advanced_sub.change_plan(DefaultProductPlan.get_default_plan_version())

        app_standard = Application.get(app_standard._id)
        app_build = Application.get(app_build._id)

        self.assertFalse(LOGO_HOME in app_standard.logo_refs)
        self.assertFalse(LOGO_LOGIN in app_standard.logo_refs)
        self.assertFalse(LOGO_HOME in app_build.logo_refs)
        self.assertFalse(LOGO_LOGIN in app_build.logo_refs)

        community_sub.change_plan(
            DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        )

        app_standard = Application.get(app_standard._id)
        app_build = Application.get(app_build._id)

        self.assertTrue(LOGO_HOME in app_standard.logo_refs)
        self.assertTrue(LOGO_LOGIN in app_standard.logo_refs)
        self.assertTrue(LOGO_HOME in app_build.logo_refs)
        self.assertTrue(LOGO_LOGIN in app_build.logo_refs)

    def test_report_builder_datasource_deactivation(self):

        def _get_data_source(id_):
            return get_datasource_config(id_, self.project.name)[0]

        # Upgrade the domain
        # (for the upgrade to work, there has to be an existing subscription,
        # which is why we subscribe to advanced first)
        self._subscribe_to_advanced()
        pro_with_rb_sub = self._subscribe_to_pro_with_rb()

        # Create reports and data sources
        builder_report_data_source = DataSourceConfiguration(
            domain=self.project.name,
            is_deactivated=False,
            referenced_doc_type="XFormInstance",
            table_id="foo",
        )
        other_data_source = DataSourceConfiguration(
            domain=self.project.name,
            is_deactivated=False,
            referenced_doc_type="XFormInstance",
            table_id="bar",
        )
        builder_report_data_source.save()
        other_data_source.save()
        report_builder_report = ReportConfiguration(
            domain=self.project.name,
            config_id=builder_report_data_source._id,
            report_meta=ReportMeta(created_by_builder=True),
        )
        report_builder_report.save()

        # downgrade the domain
        community_sub = pro_with_rb_sub.change_plan(DefaultProductPlan.get_default_plan_version())

        # Check that the builder data source is deactivated
        builder_report_data_source = _get_data_source(builder_report_data_source._id)
        self.assertTrue(builder_report_data_source.is_deactivated)
        # Check that the other data source has not been deactivated
        other_data_source = _get_data_source(other_data_source._id)
        self.assertFalse(other_data_source.is_deactivated)

        # upgrade the domain
        # (for the upgrade to work, there has to be an existing subscription,
        # which is why we subscribe to advanced first)
        community_sub.change_plan(
            DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        )
        pro_with_rb_sub = self._subscribe_to_pro_with_rb()

        # check that the data source is activated
        builder_report_data_source = _get_data_source(builder_report_data_source._id)
        self.assertFalse(builder_report_data_source.is_deactivated)

        # delete the data sources
        builder_report_data_source.delete()
        other_data_source.delete()
        # Delete the report
        report_builder_report.delete()

        # reset the subscription
        pro_with_rb_sub.change_plan(DefaultProductPlan.get_default_plan_version())

    def tearDown(self):
        self.project.delete()
        super(TestSubscriptionPermissionsChanges, self).tearDown()
