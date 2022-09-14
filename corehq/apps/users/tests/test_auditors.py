from django.test import TestCase

from corehq.apps.users.auditors import HQAuditor


class TestHQAudit(TestCase):

    def setUp(self):
        self.auditor = HQAuditor()

    def test_change_context_returns_none_when_not_authenticated(self):
        request = MockRequest.without_auth("test@example.com", "WebUser")
        self.assertIsNone(self.auditor.change_context(request))

    def test_change_context_contains_user_name_and_type(self):
        request = MockRequest.with_auth("test@example.com", "WebUser")
        self.assertEqual(
            {"username": "test@example.com", "user_type": "WebUser"},
            self.auditor.change_context(request)
        )

    def test_change_context_contains_domain_when_present(self):
        request = MockRequest.with_auth_and_domain("test@example.com", "WebUser", "test")
        self.assertEqual(
            {"username": "test@example.com", "user_type": "WebUser", "domain": "test"},
            self.auditor.change_context(request)
        )


class MockRequest:

    def __init__(self, user, couch_user, domain=None):
        self.user = user
        self.couch_user = couch_user
        if domain is not None:
            self.domain = domain

    @classmethod
    def without_auth(cls, username, doc_type):
        return cls(MockDjangoAuthUser(username, False), MockCouchUser(username, doc_type))

    @classmethod
    def with_auth(cls, username, doc_type):
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
