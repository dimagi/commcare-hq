import os
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from corehq.apps.accounting.models import (
    BillingAccount,
    BillingContactInfo,
    Subscription,
)
from corehq.apps.domain.dbaccessors import domain_or_deleted_domain_exists
from corehq.apps.domain.exceptions import ErrorInitializingDomain
from corehq.apps.domain.models import Domain
from corehq.apps.domain.tests.test_utils import domain_tombstone_patch, suspend
from corehq.apps.hqmedia.models import (
    CommCareImage,
    LogoForSystemEmailsReference,
)
from corehq.apps.hqmedia.views import ViewMultimediaFile
from corehq.apps.registration.models import SelfSignupWorkflow
from corehq.apps.registration.utils import (
    project_logo_emails_context,
    request_new_domain,
)
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled
from corehq.util.view_utils import absolute_reverse

real_BillingContactInfo_get_or_create = BillingContactInfo.objects.get_or_create


def _issue_initializing_domain(*args, **kwargs):
    # Create object, then raise excpetion. This will cause
    # _setup_subscription to fail, but SQL objects related to the domain
    # will have been saved to the database. They should be cleaned up on
    # transaction rollback due to the exception.
    real_BillingContactInfo_get_or_create(*args, **kwargs)
    raise Exception()


def _noop(*args, **kwargs):
    pass


@mock.patch('corehq.apps.registration.utils.notify_exception', _noop)
class TestRequestNewDomain(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.username = 'new@dimagi.org'
        cls.request = RequestFactory().get('/registration')
        cls.domain_sso_test = 'test-sso-1'
        cls.domain_test = 'test-1'

    def setUp(self):
        def delete_user_if_exists():
            user = WebUser.get_by_username(self.username)
            if user is not None:
                # normally it will be deleted when the domain is deleted
                user.delete(None, None)
        self.new_user = WebUser.create(None, self.username, 'testpwd', None, None)
        self.request.user = User.objects.get(username=self.username)
        self.addClassCleanup(delete_user_if_exists)

    def tearDown(self):
        subscribed_domains = [self.domain_sso_test, self.domain_test]
        for domain in subscribed_domains:
            Subscription.clear_caches(domain)
            SelfSignupWorkflow.get_in_progress_for_domain.clear(SelfSignupWorkflow, domain)
        super().tearDown()

    # if we don't patch the following, NoBrokersAvailable is thrown due to publish_domain_saved
    @mock.patch('corehq.apps.registration.utils._setup_subscription', _noop)
    def test_domain_is_active_for_new_sso_user(self):
        """
        Ensure that the first domain created by a new SSO user is active.
        """
        self.addCleanup(_cleanup_domain, 'test-sso-1')
        domain_name = request_new_domain(
            self.request,
            'test-sso-1',
            is_new_user=True,
            is_new_sso_user=True,
        )
        self.addCleanup(_cleanup_domain, domain_name)  # possibly not 'test-sso-1'
        domain = Domain.get_by_name(domain_name)
        self.assertTrue(domain.is_active)

    # if we don't patch the following, NoBrokersAvailable is thrown due to publish_domain_saved
    @mock.patch('corehq.apps.registration.utils._setup_subscription', _noop)
    def test_domain_is_not_active_for_new_user(self):
        """
        Ensure that the first domain created by a new user is not active.
        """
        self.addCleanup(_cleanup_domain, 'test-sso-2')
        domain_name = request_new_domain(
            self.request,
            'test-sso-2',
            is_new_user=True,
        )
        self.addCleanup(_cleanup_domain, domain_name)  # possibly not 'test-sso-2'
        domain = Domain.get_by_name(domain_name)
        self.assertFalse(domain.is_active)

    @suspend(domain_tombstone_patch)
    @mock.patch.object(BillingContactInfo.objects, 'get_or_create', _issue_initializing_domain)
    def test_subscription_exception_raises_error_and_domain_is_deleted(self):
        # We want to ensure that errors during the Subscription initialization process
        # do not result in incomplete domains (a domain without a Subscription)
        def check_preconditions():
            # verify that accounting models created during domain setup do not exist
            Subscription.clear_caches(domain_name)
            self.assertFalse(domain_or_deleted_domain_exists(domain_name))
            self.assertIsNone(BillingAccount.get_account_by_domain(domain_name))
            self.assertIsNone(Subscription.get_active_subscription_by_domain(domain_name))

        domain_name = 'subscription-failed'
        self.addCleanup(_cleanup_domain, domain_name)
        check_preconditions()

        with self.assertRaisesMessage(ErrorInitializingDomain,
                                      "Subscription setup failed for 'subscription-failed'"):
            request_new_domain(self.request, domain_name, is_new_user=True)

        check_preconditions()

    @mock.patch('corehq.apps.registration.utils._setup_subscription', _noop)
    @mock.patch('django.conf.settings.IS_SAAS_ENVIRONMENT', True)
    def test_saas_environment_creates_self_signup_workflow(self):
        self.addCleanup(_cleanup_domain, self.domain_test)
        domain_name = request_new_domain(
            self.request,
            self.domain_test,
            is_new_user=True,
        )
        self.addCleanup(_cleanup_domain, domain_name)  # possibly not self.domain_test
        workflow = SelfSignupWorkflow.get_in_progress_for_domain(domain_name)
        self.assertIsInstance(workflow, SelfSignupWorkflow)
        self.assertEqual(workflow.initiating_user, self.new_user.username)


class TestUsingProjectLogoInEmails(TestCase):

    def setUp(self):
        self.domain = 'hogwarts'

        # Just use favicon as an arbitrary image for testing
        image_path = os.path.join('corehq', 'apps', 'hqwebapp', 'static', 'hqwebapp', 'images', 'favicon.png')
        with open(image_path, 'rb') as f:
            image_data = f.read()
            self.image = CommCareImage.get_by_data(image_data)
            self.image.save()
            self.addCleanup(self.image.delete)

        LogoForSystemEmailsReference.objects.create(
            domain=self.domain,
            image_id=self.image._id
        )

    @flag_enabled('USE_LOGO_IN_SYSTEM_EMAILS')
    def test_project_logo_emails_context_ff_on(self):
        self.assertDictEqual(
            project_logo_emails_context(self.domain),
            {
                "base_container_template": "registration/email/base_templates/_base_container_project_logo.html",
                "link_to_logo": absolute_reverse(
                    ViewMultimediaFile.urlname, args=['CommCareImage', self.image._id])
            }
        )

    def test_project_logo_emails_context_ff_off(self):
        self.assertDictEqual(
            project_logo_emails_context(self.domain),
            {}
        )


def _cleanup_domain(name):
    domain = Domain.get_by_name(name)
    if domain is not None:
        domain.delete(leave_tombstone=False)
