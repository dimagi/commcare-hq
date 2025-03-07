import os
from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from corehq.apps.accounting.models import Subscription
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


def _issue_initializing_domain(*args, **kwargs):
    raise Exception()


def _noop(*args, **kwargs):
    pass


class TestRequestNewDomain(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.new_user = WebUser.create(
            None, 'new@dimagi.org', 'testpwd', None, None
        )
        cls.request = RequestFactory().get('/registration')
        django_user = User.objects.get(username=cls.new_user.username)
        cls.request.user = django_user
        cls.domain_sso_test = 'test-sso-1'
        cls.domain_test = 'test-1'

    def tearDown(self):
        subscribed_domains = [self.domain_sso_test, self.domain_test]
        for domain in subscribed_domains:
            Subscription._get_active_subscription_by_domain.clear(
                Subscription,
                domain
            )
        SelfSignupWorkflow.objects.filter(domain__in=subscribed_domains).delete()

        failed_subscribed_domains = ['subscription-failed', 'init-default-roles-failed']
        for test_domain in failed_subscribed_domains:
            domain = Domain.get_by_name(test_domain)
            if domain is not None:
                domain.delete()

        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.new_user.delete(cls.domain_test, deleted_by=None)
        super().tearDownClass()

    # if we don't patch the following, NoBrokersAvailable is thrown due to publish_domain_saved
    @mock.patch('corehq.apps.registration.utils._setup_subscription', _noop)
    @mock.patch('corehq.apps.registration.utils.notify_exception', _noop)
    def test_domain_is_active_for_new_sso_user(self):
        """
        Ensure that the first domain created by a new SSO user is active.
        """
        domain_name = request_new_domain(
            self.request,
            'test-sso-1',
            is_new_user=True,
            is_new_sso_user=True,
        )
        domain = Domain.get_by_name(domain_name)
        self.assertTrue(domain.is_active)

    # if we don't patch the following, NoBrokersAvailable is thrown due to publish_domain_saved
    @mock.patch('corehq.apps.registration.utils._setup_subscription', _noop)
    @mock.patch('corehq.apps.registration.utils.notify_exception', _noop)
    def test_domain_is_not_active_for_new_user(self):
        """
        Ensure that the first domain created by a new user is not active.
        """
        domain_name = request_new_domain(
            self.request,
            'test-sso-2',
            is_new_user=True,
        )
        domain = Domain.get_by_name(domain_name)
        self.assertFalse(domain.is_active)

    @suspend(domain_tombstone_patch)
    @mock.patch('corehq.apps.registration.utils._setup_subscription', _issue_initializing_domain)
    @mock.patch('corehq.apps.registration.utils.notify_exception', _noop)
    def test_subscription_exception_raises_error_and_domain_is_deleted(self):
        # We want to ensure that errors during the Subscription initialization process
        # do not result in incomplete domains (a domain without a Subscription)
        with self.assertRaisesMessage(ErrorInitializingDomain,
                                      "Subscription setup failed for 'subscription-failed'"):
            request_new_domain(
                self.request,
                'subscription-failed',
                is_new_user=True,
            )
        self.assertFalse(domain_or_deleted_domain_exists('subscription-failed'))

    @mock.patch('corehq.apps.registration.utils._setup_subscription', _noop)
    @mock.patch('corehq.apps.registration.utils.notify_exception', _noop)
    @mock.patch('django.conf.settings.IS_SAAS_ENVIRONMENT', True)
    def test_saas_environment_creates_self_signup_workflow(self):
        request_new_domain(
            self.request,
            self.domain_test,
            is_new_user=True,
        )
        workflow = SelfSignupWorkflow.get_in_progress_for_domain(self.domain_test)
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
