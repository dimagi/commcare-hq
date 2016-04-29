import os
import json
from corehq.apps.accounting import generator
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, \
    SoftwarePlanEdition, Subscription
from corehq.apps.accounting.tests import BaseAccountingTest
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.models import Domain
from corehq.apps.userreports.models import DataSourceConfiguration, \
    ReportConfiguration, ReportMeta, get_datasource_config


class TestSubscriptionPermissionsChanges(BaseAccountingTest):

    def setUp(self):
        super(TestSubscriptionPermissionsChanges, self).setUp()
        self.project = Domain(
            name="test-sub-changes",
            is_active=True,
        )
        self.project.save()

        self.admin_user = generator.arbitrary_web_user()
        self.admin_user.add_domain_membership(self.project.name, is_admin=True)
        self.admin_user.save()

        self.account = BillingAccount.get_or_create_account_by_domain(
            self.project.name, created_by=self.admin_user.username)[0]
        self.advanced_plan = DefaultProductPlan.get_default_plan_by_domain(
            self.project.name, edition=SoftwarePlanEdition.ADVANCED)

    def _subscribe_to_advanced(self):
        return Subscription.new_domain_subscription(
            self.account, self.project.name, self.advanced_plan,
            web_user=self.admin_user.username
        )


    def test_app_icon_permissions(self):
        LOGO_HOME = u'hq_logo_android_home'
        LOGO_LOGIN = u'hq_logo_android_login'

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

        self._subscribe_to_advanced()

        app_standard = Application.get(app_standard._id)
        app_build = Application.get(app_build._id)

        self.assertTrue(LOGO_HOME in app_standard.logo_refs.keys())
        self.assertTrue(LOGO_LOGIN in app_standard.logo_refs.keys())
        self.assertTrue(LOGO_HOME in app_build.logo_refs.keys())
        self.assertTrue(LOGO_LOGIN in app_build.logo_refs.keys())

    def test_report_builder_datasource_deactivation(self):

        def _get_data_source(id_):
            return get_datasource_config(id_, self.project.name)[0]

        # Upgrade the domain
        advanced_sub = self._subscribe_to_advanced()

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
        advanced_sub.cancel_subscription(web_user=self.admin_user.username)

        # Check that the builder data source is deactivated
        builder_report_data_source = _get_data_source(builder_report_data_source._id)
        self.assertTrue(builder_report_data_source.is_deactivated)
        # Check that the other data source is not deactivate
        other_data_source = _get_data_source(other_data_source._id)
        self.assertFalse(other_data_source.is_deactivated)

        # upgrade the domain
        advanced_sub = self._subscribe_to_advanced()

        # check that the data source is activated
        builder_report_data_source = _get_data_source(builder_report_data_source._id)
        self.assertFalse(builder_report_data_source.is_deactivated)

        # delete the data sources
        builder_report_data_source.delete()
        other_data_source.delete()
        report_builder_report.delete()

        # reset the subscription
        advanced_sub.cancel_subscription(web_user=self.admin_user.username)

    def tearDown(self):
        self.project.delete()
        self.admin_user.delete()
        generator.delete_all_subscriptions()
        generator.delete_all_accounts()
        super(TestSubscriptionPermissionsChanges, self).tearDown()
