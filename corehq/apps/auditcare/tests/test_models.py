from contextlib import contextmanager
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.test.utils import override_settings
from testil import Config, eq

import corehq.apps.auditcare.models as mod
from corehq.apps.auditcare.models import AccessAudit, NavigationEventAudit

from .test_middleware import make_view
from .testutils import AuditcareTest
from ..utils import to_django_header

TRACE_HEADER = "X-Test-1354321354-Trace-Id"


class TestAccessAudit(AuditcareTest):

    def test_audit_login_should_set_properties(self):
        with intercept_save(AccessAudit) as cfg:
            AccessAudit.audit_login(make_request("/a/block/login"), make_user())
            event = cfg.obj
        self.assertEqual(event.user, "melvin@test.com")
        self.assertEqual(event.path, "/a/block/login")
        self.assertEqual(event.domain, "block")
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
        self.assertEqual(event.domain, "block")
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
        self.assertEqual(event.domain, None)
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

    @override_settings(AUDIT_TRACE_ID_HEADER=TRACE_HEADER)
    def test_audit_trace_id_header(self):
        trace_id = "Root=1-67891233-abcdef012345678912345678"
        headers = {to_django_header(TRACE_HEADER): trace_id}
        request = make_request("/a/block/login", **headers)

        # HACK verify that the header was set correctly
        assert TRACE_HEADER in request.headers, request.headers

        with intercept_save(AccessAudit) as cfg, patch_trace_id_header():
            AccessAudit.audit_login(request, None)
            event = cfg.obj
        self.assertEqual(event.trace_id, trace_id)


class TestNavigationEventAudit(AuditcareTest):

    def test_audit_view_should_set_properties(self):
        path = "/a/block/path"
        view = make_view(path)
        request = make_request(path)
        event = NavigationEventAudit.audit_view(request, "melvin@test.com", view, {})
        self.assertEqual(event.path, path)
        self.assertEqual(event.domain, "block")
        self.assertEqual(event.request_path, f"{path}?key=value")
        self.assertEqual(event.description, "melvin@test.com")
        self.assertNotIn(to_django_header(TRACE_HEADER), event.headers)
        event.save()

    def test_audit_view_should_truncate_params(self):
        path = "/path"
        view = make_view(path)
        request = make_request(path, params={f"a{x}": "b" for x in range(1000)})
        event = NavigationEventAudit.audit_view(request, "melvin@test.com", view, {})
        event.save()
        event.refresh_from_db()
        self.assertEqual(len(event.params), 4096)

    @override_settings(AUDIT_TRACE_ID_HEADER=TRACE_HEADER)
    def test_audit_trace_id_header(self):
        trace_id = "Root=1-67891233-abcdef012345678912345678"
        with patch_trace_id_header():
            view = make_view()
            request = make_request(**{to_django_header(TRACE_HEADER): trace_id})
            event = NavigationEventAudit.audit_view(request, "melvin@test.com", view, {})
        self.assertEqual(event.headers[to_django_header(TRACE_HEADER)], trace_id)
        event.save()

    def test_audit_view_should_not_save(self):
        view = make_view()
        event = NavigationEventAudit.audit_view(make_request(), "melvin@test.com", view, {})
        self.assertIsNone(event.id)


def test_get_domain():
    def test(cfg):
        request = make_request(cfg.path)
        if "request_domain" in cfg:
            request.domain = cfg.request_domain
        eq(mod.get_domain(request), cfg.expect)

    cfg = Config(expect="block")
    yield test, cfg(path="/path", expect=None)
    yield test, cfg(path="/a/block/path")
    yield test, cfg(path="/path", request_domain="block")
    yield test, cfg(path="/a/block/path", request_domain="xx")


def make_request(path="/path", session_key="abc", params=None, **headers):
    headers.setdefault("HTTP_ACCEPT", "html")
    headers.setdefault("HTTP_USER_AGENT", "Mozilla")
    request = RequestFactory().get(path, params or {"key": "value"}, **headers)
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


@contextmanager
def patch_trace_id_header():
    def assert_not_installed():
        assert AccessAudit.trace_id_header != settings.AUDIT_TRACE_ID_HEADER, \
            AccessAudit.trace_id_header
        assert django_header not in mod.STANDARD_HEADER_KEYS, \
            (django_header, mod.STANDARD_HEADER_KEYS)

    from .. import install_trace_id_header
    django_header = to_django_header(settings.AUDIT_TRACE_ID_HEADER)
    assert_not_installed()
    install_trace_id_header()
    try:
        yield
    finally:
        AccessAudit.trace_id_header = None
        mod.STANDARD_HEADER_KEYS.remove(django_header)
        assert_not_installed()
