from unittest.mock import patch

from django.test import TestCase

from corehq.apps.users.auditors import HQAuditor


class TestHQAudit(TestCase):

    def setUp(self):
        self.auditor = HQAuditor()

    def test_change_context_returns_none_when_not_authenticated(self):
        request = MockRequest.without_auth("test@example.com")
        self.assertIsNone(self.auditor.change_context(request))

    def test_change_context_contains_user_name_and_type(self):
        request = MockRequest.with_auth_and_couch_user("test@example.com", "WebUser")
        self.assertEqual(
            {"username": "test@example.com", "user_type": "WebUser"},
            self.auditor.change_context(request)
        )

    def test_change_context_fetches_couch_user_when_missing(self):
        request = MockRequest.with_auth("test@example.com")
        couch_user = MockCouchUser(request.user.username, "WebUser")
        with patch("corehq.apps.users.models.CouchUser.get_by_username", return_value=couch_user) as mock:
            change_context = self.auditor.change_context(request)
            mock.assert_called_once_with(request.user.username)
        self.assertEqual(
            {"username": "test@example.com", "user_type": "WebUser"},
            change_context,
        )

    def test_change_context_contains_domain_when_present(self):
        request = MockRequest.with_auth_and_domain("test@example.com", "WebUser", "test")
        self.assertEqual(
            {"username": "test@example.com", "user_type": "WebUser", "domain": "test"},
            self.auditor.change_context(request)
        )


class MockRequest:

    def __init__(self, user, couch_user=None, domain=None):
        self.user = user
        if couch_user is not None:
            self.couch_user = couch_user
        if domain is not None:
            self.domain = domain

    @classmethod
    def without_auth(cls, username):
        return cls(MockDjangoAuthUser(username, False))

    @classmethod
    def with_auth(cls, username):
        return cls(MockDjangoAuthUser(username))

    @classmethod
    def with_auth_and_couch_user(cls, username, doc_type):
        return cls(MockDjangoAuthUser(username), MockCouchUser(username, doc_type))

    @classmethod
    def with_auth_and_domain(cls, username, doc_type, domain):
        return cls(MockDjangoAuthUser(username), MockCouchUser(username, doc_type), domain)


class MockDjangoAuthUser:

    def __init__(self, username, is_authenticated=True):
        self.username = username
        self.is_authenticated = is_authenticated


class MockCouchUser:

    def __init__(self, username, doc_type):
        self.username = username
        self.doc_type = doc_type
