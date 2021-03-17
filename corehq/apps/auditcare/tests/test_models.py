from contextlib import contextmanager
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory
from testil import Config

import corehq.apps.auditcare.models as mod
from corehq.apps.auditcare.models import AccessAudit, NavigationEventAudit

from .test_middleware import make_view
from .testutils import AuditcareTest


class TestAccessAudit(AuditcareTest):

    def test_audit_login_should_set_properties(self):
        with intercept_save(AccessAudit) as cfg:
            AccessAudit.audit_login(make_request("/a/block/login"), make_user())
            event = cfg.obj
        self.assertEqual(event.user, "melvin@test.com")
        self.assertEqual(event.path, "/a/block/login")
        self.assertEqual(event.ip_address, "127.0.0.1")
        self.assertEqual(event.http_accept, "html")
        self.assertEqual(event.user_agent, "Mozilla")
        self.assertEqual(event.access_type, mod.ACCESS_LOGIN)
        self.assertEqual(event.session_key, "abc")
        self.assertEqual(event.description, "Login: melvin@test.com")

    def test_audit_login_failed_should_set_properties(self):
        request = make_request("/a/block/login", session_key=None)
        with intercept_save(AccessAudit) as cfg:
            AccessAudit.audit_login_failed(request, "melvin@test.com")
            event = cfg.obj
        self.assertEqual(event.user, "melvin@test.com")
        self.assertEqual(event.path, "/a/block/login")
        self.assertEqual(event.ip_address, "127.0.0.1")
        self.assertEqual(event.http_accept, "html")
        self.assertEqual(event.user_agent, "Mozilla")
        self.assertEqual(event.access_type, mod.ACCESS_FAILED)
        self.assertEqual(event.session_key, None)
        self.assertEqual(event.description, "Login failed: melvin@test.com")

    def test_audit_logout_should_set_properties(self):
        with intercept_save(AccessAudit) as cfg:
            AccessAudit.audit_logout(make_request("/accounts/logout"), make_user())
            event = cfg.obj
        self.assertEqual(event.user, "melvin@test.com")
        self.assertEqual(event.path, "/accounts/logout")
        self.assertEqual(event.ip_address, "127.0.0.1")
        self.assertEqual(event.http_accept, "html")
        self.assertEqual(event.user_agent, "Mozilla")
        self.assertEqual(event.access_type, mod.ACCESS_LOGOUT)
        self.assertEqual(event.session_key, "abc")
        self.assertEqual(event.description, "Logout: melvin@test.com")

    def test_audit_logout_anonymous_should_set_properties(self):
        with intercept_save(AccessAudit) as cfg:
            AccessAudit.audit_logout(make_request("/accounts/logout"), None)
            event = cfg.obj
        self.assertEqual(event.user, None)
        self.assertEqual(event.description, "Logout: ")


class TestNavigationEventAudit(AuditcareTest):

    def test_should_create_event_with_path(self):
        view = make_view()
        event = NavigationEventAudit.audit_view(make_request(), "melvin@test.com", view, {})
        self.assertEqual(event.path, "/path")
        self.assertEqual(event.request_path, "/path?key=value")
        self.assertEqual(event.description, "melvin@test.com")
        event.save()

    def test_audit_view_should_not_save(self):
        view = make_view()
        event = NavigationEventAudit.audit_view(make_request(), "melvin@test.com", view, {})
        self.assertIsNone(event.id)


def make_request(path="/path", session_key="abc"):
    request = RequestFactory().get(path, {"key": "value"})
    request.META["HTTP_ACCEPT"] = "html"
    request.META["HTTP_USER_AGENT"] = "Mozilla"
    request.session = Config(session_key=session_key)
    return request


def make_user():
    return User(username="melvin@test.com", first_name="Melvin", last_name="Block")


@contextmanager
def intercept_save(cls):
    def save(self):
        real_save(self)
        config.obj = self

    config = Config()
    real_save = cls.save
    with patch.object(cls, "save", save):
        yield config
