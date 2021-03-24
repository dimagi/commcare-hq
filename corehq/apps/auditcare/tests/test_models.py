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

TRACE_HEADER = "X-Test-Trace-Id"


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

    def test_delete_duplicates(self):
        from itertools import groupby
        from django.db import models
        from ..models import UserAgent, HttpAccept, ViewName

        model_map = {
            HttpAccept: [AccessAudit],
            UserAgent: [AccessAudit, NavigationEventAudit],
            ViewName: [NavigationEventAudit],
        }
        field_map = {
            HttpAccept: "http_accept_fk_id",
            UserAgent: "user_agent_fk_id",
            ViewName: "view_fk_id",
        }

        def delete_duplicates(model):
            def update_dups(rel_model, first_id, other_ids):
                field_name = field_map[model]
                rel_model.objects.filter(
                    **{field_name + "__in": other_ids}
                ).update(
                    **{field_name: first_id},
                )

            def do_delete(apps, schema_editor):
                def sort_key(item):
                    id, value = item
                    return value

                dup_values = list(
                    model.objects
                    .values("value")
                    .annotate(value_count=models.Count("value"))
                    .filter(value_count__gt=1)
                    .values_list("value", flat=True)
                )
                dups = (
                    model.objects
                    .filter(value__in=dup_values)
                    .values_list("id", "value")
                )
                for value, pairs in groupby(sorted(dups, key=sort_key), key=sort_key):
                    ids = sorted(id for id, value in pairs)
                    first_id, *other_ids = ids
                    for rel_model in model_map[model]:
                        update_dups(rel_model, first_id, other_ids)
                    model.objects.filter(value=value, id__in=other_ids).delete()

            return do_delete

        values = [
            UserAgent(value="1"),
            UserAgent(value="1"),
            UserAgent(value="1"),
            UserAgent(value="2"),
            HttpAccept(value="1"),
            HttpAccept(value="1"),
            HttpAccept(value="1"),
            HttpAccept(value="2"),
            ViewName(value="1"),
            ViewName(value="1"),
            ViewName(value="1"),
            ViewName(value="2"),
        ]
        for value in values:
            value.save()
        agents = values[:4]
        accepts = values[4:8]
        views = values[8:]

        for agent, accept in zip(agents, accepts):
            acc = AccessAudit(
                user_agent_fk_id=agent.id,
                http_accept_fk_id=accept.id,
                access_type="i",
            )
            acc.save()

        for agent, view in zip(agents, views):
            nav = NavigationEventAudit(user_agent_fk_id=agent.id, view_fk_id=view.id)
            nav.save()

        delete_duplicates(UserAgent)(None, None)
        delete_duplicates(HttpAccept)(None, None)
        delete_duplicates(ViewName)(None, None)

        def assert_foreigns(model, values):
            new_values = model.objects.all()
            value_ids = {a.id for a in new_values}
            self.assertEqual(value_ids, {values[0].id, values[3].id}, values)

        assert_foreigns(UserAgent, agents)
        assert_foreigns(HttpAccept, accepts)
        assert_foreigns(ViewName, views)

        navs = NavigationEventAudit.objects.all()
        agent_ids = {n.user_agent_fk_id for n in navs}
        self.assertEqual(agent_ids, {agents[0].id, agents[3].id})
        view_ids = {n.view_fk_id for n in navs}
        self.assertEqual(view_ids, {views[0].id, views[3].id})

        accs = AccessAudit.objects.all()
        agent_ids = {n.user_agent_fk_id for n in accs}
        self.assertEqual(agent_ids, {agents[0].id, agents[3].id})
        accept_ids = {n.http_accept_fk_id for n in accs}
        self.assertEqual(accept_ids, {accepts[0].id, accepts[3].id})


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


def make_request(path="/path", session_key="abc", **headers):
    headers.setdefault("HTTP_ACCEPT", "html")
    headers.setdefault("HTTP_USER_AGENT", "Mozilla")
    request = RequestFactory().get(path, {"key": "value"}, **headers)
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
        assert AccessAudit.trace_id_header is None, AccessAudit.trace_id_header
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
