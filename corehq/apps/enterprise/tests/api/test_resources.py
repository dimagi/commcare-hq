from datetime import datetime, timezone
from unittest.mock import patch

from django.http import Http404
from django.test import RequestFactory, TestCase, SimpleTestCase

from tastypie.exceptions import ImmediateHttpResponse

from corehq.apps.accounting.models import (
    DefaultProductPlan,
    SoftwarePlanEdition,
)
from corehq.apps.accounting.tests.utils import generator
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.enterprise import (
    EnterpriseDomainReport,
    EnterpriseWebUserReport,
    EnterpriseMobileWorkerReport,
    EnterpriseSMSReport,
    EnterpriseODataReport,
    EnterpriseCaseManagementReport,
    EnterpriseDataExportReport,
    Enterprise2FAReport,
    EnterpriseCommCareVersionReport,
    EnterpriseAPIReport,
    EnterpriseDataForwardingReport,
    EnterpriseAppVersionComplianceReport,
)
from corehq.apps.enterprise.api.resources import (
    EnterpriseODataAuthentication,
    DomainResource,
    WebUserResource,
    MobileUserResource,
    ODataAuthentication,
    SMSResource,
    ODataFeedResource,
    CaseManagementResource,
    DataExportReportResource,
    TwoFactorAuthResource,
    CommCareVersionComplianceResource,
    APIKeysResource,
    DataForwardingResource,
    ApplicationVersionComplianceResource,
)
from corehq.apps.users.models import WebUser


class EnterpriseODataAuthenticationTests(TestCase):
    def setUp(self):
        super().setUp()
        patcher = patch.object(ODataAuthentication, 'is_authenticated', return_value=True)
        self.mock_is_authentication = patcher.start()
        self.addCleanup(patcher.stop)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._create_user('admin@testing-domain.com')
        cls.account = cls._create_enterprise_account_covering_domains(['testing-domain'])
        cls.account.enterprise_admin_emails = [cls.user.username]
        cls.account.save()

    def test_successful_authentication(self):
        request = self._create_request(self.user, 'testing-domain')

        auth = EnterpriseODataAuthentication()
        self.assertTrue(auth.is_authenticated(request))

    def test_parent_failure_returns_parent_results(self):
        self.mock_is_authentication.return_value = False

        request = self._create_request(self.user, 'testing-domain')

        auth = EnterpriseODataAuthentication()
        self.assertFalse(auth.is_authenticated(request))

    def test_raises_exception_when_billing_account_does_not_exist(self):
        request = self._create_request(self.user, 'not-testing-domain')

        auth = EnterpriseODataAuthentication()
        with self.assertRaises(Http404):
            auth.is_authenticated(request)

    def test_raises_exception_when_not_an_enterprise_admin(self):
        self.account.enterprise_admin_emails = ['not-this-user@testing-domain.com']
        self.account.save()

        request = self._create_request(self.user, 'testing-domain')

        auth = EnterpriseODataAuthentication()
        with self.assertRaises(ImmediateHttpResponse):
            auth.is_authenticated(request)

    @classmethod
    def _create_enterprise_account_covering_domains(cls, domains):
        billing_account = generator.billing_account(
            'test-admin@dimagi.com',
            'test-admin@dimagi.com',
            is_customer_account=True
        )

        enterprise_plan = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.ENTERPRISE)

        for domain in domains:
            domain_obj = Domain(name=domain, is_active=True)
            domain_obj.save()
            cls.addClassCleanup(domain_obj.delete)

            generator.generate_domain_subscription(
                billing_account,
                domain_obj,
                datetime.now(timezone.utc),
                None,
                plan_version=enterprise_plan,
                is_active=True
            )

        return billing_account

    @classmethod
    def _create_user(cls, username):
        return WebUser(username=username)

    def _create_request(self, user, domain):
        request = RequestFactory().get('/')
        request.couch_user = user
        request.domain = domain
        return request


class TestDomainResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseDomainReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in DomainResource.COLUMN_MAP.items()}
        expectedMapping = {
            'domain': 'Project Space Name',
            'created_on': 'Created On [UTC]',
            'num_apps': '# of Apps',
            'num_mobile_users': '# of Mobile Users',
            'num_web_users': '# of Web Users',
            'num_sms_last_30_days': '# of SMS (last 30 days)',
            'last_form_submission': 'Last Form Submission [UTC]',
            'num_odata_feeds_used': 'OData Feeds Used',
            'num_odata_feeds_available': 'OData Feeds Available',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestWebUserResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseWebUserReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in
                          WebUserResource.COLUMN_MAP.items()}
        expectedMapping = {
            'email': 'Email Address',
            'name': 'Name',
            'role': 'Role',
            'last_login': 'Last Login [UTC]',
            'last_access_date': 'Last Access Date [UTC]',
            'status': 'Status',
            'domain': 'Project Space Name',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestMobileUserResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseMobileWorkerReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in
                          MobileUserResource.COLUMN_MAP.items()}
        expectedMapping = {
            'username': 'Username',
            'name': 'Name',
            'email': 'Email Address',
            'role': 'Role',
            'created_at': 'Created Date [UTC]',
            'last_sync': 'Last Sync [UTC]',
            'last_submission': 'Last Submission [UTC]',
            'commcare_version': 'CommCare Version',
            'user_id': 'User ID',
            'domain': 'Project Space Name',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestSMSResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseSMSReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in SMSResource.COLUMN_MAP.items()}
        expectedMapping = {
            'domain': 'Project Space',
            'num_sent': '# Sent',
            'num_received': '# Received',
            'num_error': '# Errors',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestODataFeedResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseODataReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in
                          ODataFeedResource.COLUMN_MAP.items()}
        expectedMapping = {
            'domain': 'Project Space',
            'report_name': 'Name',
            'report_rows': 'Number of Rows',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestCaseManagementResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseCaseManagementReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in
                          CaseManagementResource.COLUMN_MAP.items()}
        expectedMapping = {
            'domain': 'Project Space',
            'num_applications': '# Applications',
            'num_surveys_only': '# Surveys Only',
            'num_cases_only': '# Cases Only',
            'num_mixed': '# Mixed',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestDataExportResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseDataExportReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in
                          DataExportReportResource.COLUMN_MAP.items()}
        expectedMapping = {
            'domain': 'Project Space',
            'name': 'Name',
            'export_type': 'Type',
            'export_subtype': 'SubType',
            'owner': 'Created By',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestTwoFactorAuthResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = Enterprise2FAReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in
                          TwoFactorAuthResource.COLUMN_MAP.items()}
        expectedMapping = {
            'domain_without_2fa': 'Project Space without 2FA',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestCommCareVersionComplianceResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseCommCareVersionReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in
                          CommCareVersionComplianceResource.COLUMN_MAP.items()}
        expectedMapping = {
            'mobile_worker': 'Mobile Worker',
            'domain': 'Project Space',
            'latest_version_available_at_submission': 'Latest Version Available at Submission',
            'version_in_use': 'Version in Use',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestAPIKeysResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseAPIReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in
                          APIKeysResource.COLUMN_MAP.items()}
        expectedMapping = {
            'web_user': 'Web User',
            'api_key_name': 'API Key Name',
            'scope': 'Scope',
            'expiration_date': 'Expiration Date [UTC]',
            'created_date': 'Created On [UTC]',
            'last_used_date': 'Last Used On [UTC]',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestDataForwardingResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseDataForwardingReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in
                          DataForwardingResource.COLUMN_MAP.items()}
        expectedMapping = {
            'domain': 'Project Space',
            'service_name': 'Service Name',
            'service_type': 'Type',
            'last_modified': 'Last Modified [UTC]',
        }

        self.assertEqual(header_mapping, expectedMapping)


class TestApplicationVersionComplianceResourceMapping(SimpleTestCase):
    def test_headers(self):
        report = EnterpriseAppVersionComplianceReport(None, None)

        header_mapping = {name: report.headers[index] for (name, index) in
                          ApplicationVersionComplianceResource.COLUMN_MAP.items()}
        expectedMapping = {
            'mobile_worker': 'Mobile Worker',
            'domain': 'Project Space',
            'application': 'Application',
            'latest_version_available_when_last_used': 'Latest Version Available When Last Used',
            'version_in_use': 'Version in Use',
            'last_used': 'Last Used [UTC]',
        }

        self.assertEqual(header_mapping, expectedMapping)
