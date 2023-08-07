from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.domain.exceptions import DomainDoesNotExist
from corehq.apps.linked_domain.exceptions import (
    DomainLinkAlreadyExists,
    DomainLinkError,
    DomainLinkNotAllowed,
    InvalidPushException,
    UserDoesNotHavePermission,
)
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.views import (
    check_if_push_violates_constraints,
    link_domains,
    validate_pull,
    validate_push,
)
from corehq.apps.users.models import WebUser


class LinkDomainsTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(LinkDomainsTests, cls).setUpClass()
        cls.upstream_domain = 'upstream'
        cls.downstream_domain = 'downstream'

    def test_exception_raised_if_domain_does_not_exist(self):
        def mock_handler(domain):
            return domain != self.downstream_domain

        with patch('corehq.apps.linked_domain.views.domain_exists') as mock_domainexists,\
             self.assertRaises(DomainDoesNotExist):
            mock_domainexists.side_effect = mock_handler
            link_domains(Mock(), self.upstream_domain, self.downstream_domain)

    def test_exception_raised_if_domain_link_already_exists(self):
        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=Mock()),\
             self.assertRaises(DomainLinkAlreadyExists):
            link_domains(Mock(), self.upstream_domain, self.downstream_domain)

    def test_exception_raised_if_domain_link_error_raised(self):
        def mock_handler(downstream, upstream):
            raise DomainLinkError

        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=None),\
             patch('corehq.apps.linked_domain.views.DomainLink.link_domains') as mock_linkdomains,\
             self.assertRaises(DomainLinkError):
            mock_linkdomains.side_effect = mock_handler
            link_domains(Mock(), self.upstream_domain, self.downstream_domain)

    def test_exception_raised_if_user_does_not_have_access_in_both_domains(self):
        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=None),\
             patch('corehq.apps.linked_domain.views.user_has_access_in_all_domains', return_value=False),\
             self.assertRaises(DomainLinkNotAllowed):
            link_domains(Mock(), self.upstream_domain, self.downstream_domain)

    def test_successful(self):
        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=None),\
             patch('corehq.apps.linked_domain.views.DomainLink.link_domains', return_value=True),\
             patch('corehq.apps.linked_domain.views.user_has_access_in_all_domains', return_value=True):
            domain_link = link_domains(Mock(), self.upstream_domain, self.downstream_domain)

        self.assertIsNotNone(domain_link)


class ValidatePushTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser()
        cls.user.username = 'superuser'
        cls.user.save()
        cls.addClassCleanup(cls.user.delete, 'test-domain', deleted_by=None)

        validate_patcher = patch('corehq.apps.linked_domain.views.check_if_push_violates_constraints')
        cls.mock_violates_constraints = validate_patcher.start()
        cls.addClassCleanup(validate_patcher.stop)

        permissions_check_patcher = patch('corehq.apps.linked_domain.views.user_has_access_in_all_domains')
        cls.mock_permissions_check = permissions_check_patcher.start()
        cls.addClassCleanup(permissions_check_patcher.stop)

    def test_raises_exception_if_no_downstream_domains_selected(self):
        with self.assertRaises(InvalidPushException) as cm:
            validate_push(self.user, 'upstream', [])
        self.assertEqual(cm.exception.message,
                         'No downstream project spaces were selected. Please contact support.')

    def test_raises_exception_if_link_not_found(self):
        with self.assertRaises(InvalidPushException) as cm:
            validate_push(self.user, 'upstream', ['downstream'])
        self.assertEqual(cm.exception.message,
                         "The project space link between upstream and downstream does not exist. Ensure the "
                         "link was not recently deleted.")

    def test_raises_exception_if_user_does_not_have_permission(self):
        DomainLink.objects.create(master_domain='upstream', linked_domain='downstream')
        self.mock_permissions_check.return_value = False
        with self.assertRaises(InvalidPushException) as cm:
            validate_push(self.user, 'upstream', ['downstream'])
        self.assertEqual(cm.exception.message,
                         "You do not have permission to push to all specified downstream project spaces.")

    def test_raises_exception_if_user_attempts_invalid_push(self):
        """See CheckIfPushViolatesConstraintTests for more related tests"""
        DomainLink.objects.create(master_domain='upstream', linked_domain='downstream')
        self.mock_permissions_check.return_value = True
        self.mock_violates_constraints.side_effect = InvalidPushException(message='mocked exception')

        with self.assertRaises(InvalidPushException):
            validate_push(self.user, 'upstream', ['downstream'])

    def test_successful_validation(self):
        DomainLink.objects.create(master_domain='upstream', linked_domain='downstream')
        self.mock_permissions_check.return_value = True
        self.mock_violates_constraints.side_effect = None

        validate_push(self.user, 'upstream', ['downstream'])


class CheckIfPushViolatesConstraintTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.superuser = WebUser()
        cls.superuser.username = 'superuser'
        cls.superuser.is_superuser = True
        cls.superuser.save()
        cls.addClassCleanup(cls.superuser.delete, 'test-domain', deleted_by=None)

        cls.non_superuser = WebUser()
        cls.non_superuser.username = 'nonsuperuser'
        cls.non_superuser.is_superuser = False
        cls.non_superuser.save()
        cls.addClassCleanup(cls.non_superuser.delete, 'test-domain', deleted_by=None)

    def test_superuser_can_push_multiple_full_access_links(self):
        full_access_link1 = DomainLink.objects.create(master_domain='upstream', linked_domain='full1')
        full_access_link2 = DomainLink.objects.create(master_domain='upstream', linked_domain='full2')

        link1_patcher = patch.object(full_access_link1, 'has_full_access', return_value=True)
        link1_patcher.start()
        self.addCleanup(link1_patcher.stop)

        link2_patcher = patch.object(full_access_link2, 'has_full_access', return_value=True)
        link2_patcher.start()
        self.addCleanup(link2_patcher.stop)

        # should not raise exception
        check_if_push_violates_constraints(self.superuser, [full_access_link1, full_access_link2])

    def test_non_superuser_can_push_to_multiple_full_access_links(self):
        full_access_link1 = DomainLink.objects.create(master_domain='upstream', linked_domain='full1')
        full_access_link2 = DomainLink.objects.create(master_domain='upstream', linked_domain='full2')

        link1_patcher = patch.object(full_access_link1, 'has_full_access', return_value=True)
        link1_patcher.start()
        self.addCleanup(link1_patcher.stop)

        link2_patcher = patch.object(full_access_link2, 'has_full_access', return_value=True)
        link2_patcher.start()
        self.addCleanup(link2_patcher.stop)

        # should not raise exception
        check_if_push_violates_constraints(self.non_superuser, [full_access_link1, full_access_link2])

    def test_superuser_can_push_multiple_mixed_access_links(self):
        full_access_link = DomainLink.objects.create(master_domain='upstream', linked_domain='full')
        limited_access_link = DomainLink.objects.create(master_domain='upstream', linked_domain='limited')

        link1_patcher = patch.object(full_access_link, 'has_full_access', return_value=True)
        link1_patcher.start()
        self.addCleanup(link1_patcher.stop)

        link2_patcher = patch.object(limited_access_link, 'has_full_access', return_value=False)
        link2_patcher.start()
        self.addCleanup(link2_patcher.stop)

        # should not raise exception
        check_if_push_violates_constraints(self.superuser, [full_access_link, limited_access_link])

    def test_raises_exception_if_non_superuser_pushes_to_multiple_mixed_access_links(self):
        full_access_link = DomainLink.objects.create(master_domain='upstream', linked_domain='full')
        limited_access_link = DomainLink.objects.create(master_domain='upstream', linked_domain='limited')

        link1_patcher = patch.object(full_access_link, 'has_full_access', return_value=True)
        link1_patcher.start()
        self.addCleanup(link1_patcher.stop)

        link2_patcher = patch.object(limited_access_link, 'has_full_access', return_value=False)
        link2_patcher.start()
        self.addCleanup(link2_patcher.stop)

        with self.assertRaises(InvalidPushException) as cm:
            check_if_push_violates_constraints(self.non_superuser, [full_access_link, limited_access_link])
        self.assertEqual(cm.exception.message,
                         "The attempted push is disallowed because it includes the following domains that can "
                         "only be pushed to one at a time: limited")

    def test_superuser_can_push_multiple_limited_access_links(self):
        limited_access_link1 = DomainLink.objects.create(master_domain='upstream', linked_domain='limited1')
        limited_access_link2 = DomainLink.objects.create(master_domain='upstream', linked_domain='limited2')

        link1_patcher = patch.object(limited_access_link1, 'has_full_access', return_value=False)
        link1_patcher.start()
        self.addCleanup(link1_patcher.stop)

        link2_patcher = patch.object(limited_access_link2, 'has_full_access', return_value=False)
        link2_patcher.start()
        self.addCleanup(link2_patcher.stop)

        # should not raise exception
        check_if_push_violates_constraints(self.superuser, [limited_access_link1, limited_access_link2])

    def test_raises_exception_if_non_superuser_pushes_to_multiple_limited_access_links(self):
        limited_access_link1 = DomainLink.objects.create(master_domain='upstream', linked_domain='limited1')
        limited_access_link2 = DomainLink.objects.create(master_domain='upstream', linked_domain='limited2')

        link1_patcher = patch.object(limited_access_link1, 'has_full_access', return_value=False)
        link1_patcher.start()
        self.addCleanup(link1_patcher.stop)

        link2_patcher = patch.object(limited_access_link2, 'has_full_access', return_value=False)
        link2_patcher.start()
        self.addCleanup(link2_patcher.stop)

        with self.assertRaises(InvalidPushException) as cm:
            check_if_push_violates_constraints(self.non_superuser, [limited_access_link1, limited_access_link2])
        self.assertEqual(cm.exception.message,
                         "The attempted push is disallowed because it includes the following domains that can "
                         "only be pushed to one at a time: limited1, limited2")


class ValidatePullTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser()
        cls.user.username = 'user'
        cls.user.is_superuser = False
        cls.user.save()
        cls.addClassCleanup(cls.user.delete, 'test-domain', deleted_by=None)

        permissions_check_patcher = patch('corehq.apps.linked_domain.views.user_has_access')
        cls.mock_permissions_check = permissions_check_patcher.start()
        cls.addClassCleanup(permissions_check_patcher.stop)

    def test_raises_exception_if_user_does_not_have_permission(self):
        domain_link = DomainLink.objects.create(master_domain='upstream', linked_domain='downstream')
        self.mock_permissions_check.return_value = False
        with self.assertRaises(UserDoesNotHavePermission):
            validate_pull(self.user, domain_link)

    def test_successful_if_user_has_permission_in_downstream_domain_only(self):
        domain_link = DomainLink.objects.create(master_domain='upstream', linked_domain='downstream')
        self.mock_permissions_check.side_effect = lambda user, domain: domain == 'downstream'

        try:
            validate_pull(self.user, domain_link)
        except UserDoesNotHavePermission:
            self.fail("Unexpected exception UserDoesNotHavePermission raised")
