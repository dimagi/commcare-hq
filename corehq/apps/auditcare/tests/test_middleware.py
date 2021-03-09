from contextlib import contextmanager
from unittest.mock import patch

from django.conf import settings as default_settings
from django.test import SimpleTestCase
from testil import Config, eq

from .. import middleware as mod


class TestAuditMiddleware(SimpleTestCase):

    def test_generic_view_not_audited_with_default_settings(self):
        req, func = make_view()
        with configured_middleware() as ware:
            ware.process_view(req, func, ARGS, KWARGS)
        self.assert_no_audit(req)

    def test_admin_view_is_audited_with_default_settings(self):
        req, func = make_view(module="django.contrib.admin")
        with configured_middleware() as ware:
            ware.process_view(req, func, ARGS, KWARGS)
        self.assert_audit(req)

    def test_generic_view_is_audited_with_audit_all_views_setting(self):
        req, func = make_view()
        settings = Settings(AUDIT_ALL_VIEWS=True)
        with configured_middleware(settings) as ware:
            ware.process_view(req, func, ARGS, KWARGS)
        self.assert_audit(req)

    def test_generic_view_class_is_audited_with_audit_all_views_setting(self):
        req, func = make_view("TheView")
        settings = Settings(AUDIT_ALL_VIEWS=True)
        with configured_middleware(settings) as ware:
            ware.process_view(req, func, ARGS, KWARGS)
        self.assert_audit(req)

    def test_audit_views_setting(self):
        req, func = make_view("ChangeMyPasswordView", "corehq.apps.settings.views")
        with configured_middleware() as ware:
            ware.process_view(req, func, ARGS, KWARGS)
        self.assert_audit(req)

    def test_audit_modules_setting(self):
        req, func = make_view("TheView", "corehq.apps.reports")
        with configured_middleware() as ware:
            ware.process_view(req, func, ARGS, KWARGS)
        self.assert_audit(req)

    def test_debug_media_view_not_audited(self):
        req, func = make_view("debug_media", "debug_toolbar.views")
        with configured_middleware() as ware:
            ware.process_view(req, func, ARGS, KWARGS)
        self.assert_no_audit(req)

    def test_staticfiles_not_audited(self):
        from django.contrib.staticfiles.views import serve
        req = Config(user="username")
        with configured_middleware() as ware:
            ware.process_view(req, serve, ARGS, KWARGS)
        self.assert_no_audit(req)

    def assert_audit(self, request):
        audit_doc = getattr(request, "audit_doc", None)
        self.assertEqual(audit_doc, EXPECTED_AUDIT, "audit expected")

    def assert_no_audit(self, request):
        self.assertFalse(hasattr(request, "audit_doc"), "unexpected audit")


def test_make_view_function():
    req, func = make_view()
    eq(req.user, "username")
    eq(func.__name__, "the_view")
    eq(func.__module__, "corehq.apps.auditcare.views")


def test_make_view_class():
    req, func = make_view("TheView")
    eq(req.user, "username")
    eq(func.__class__.__name__, "TheView")
    eq(func.__module__, "corehq.apps.auditcare.views")


def test_make_admin_view_function():
    req, func = make_view("the_view", "django.contrib.admin")
    eq(req.user, "username")
    eq(func.__name__, "the_view")
    eq(func.__module__, "django.contrib.admin")


def test_make_admin_view_class():
    req, func = make_view("TheView", "django.contrib.admin")
    eq(req.user, "username")
    eq(func.__class__.__name__, "TheView")
    eq(func.__module__, "django.contrib.admin")


ARGS = ()  # positional view args are not audited, therefore are empty
KWARGS = {"non": "empty", "and": "audited", "view": "kwargs"}
EXPECTED_AUDIT = Config(user="username", view_kwargs=KWARGS)
Settings = Config(
    AUDIT_MODULES=default_settings.AUDIT_MODULES,
    AUDIT_VIEWS=default_settings.AUDIT_VIEWS,
)


@contextmanager
def configured_middleware(settings=Settings):
    with patch.object(mod.NavigationEventAudit, "audit_view", fake_audit), \
            patch.object(mod, "settings", settings):
        yield mod.AuditMiddleware(None)


def make_view(name="the_view", module="corehq.apps.auditcare.views"):
    is_class = name[0].isupper()
    if is_class:
        view_func = type(name, (), {})()
    else:
        def view_func():
            assert False, "unexpected call"
        view_func.__name__ = name
    view_func.__module__ = module
    request = Config(user="username")
    return request, view_func


def fake_audit(request, user, view_func, view_kwargs, extra={}):
    return Config(user=user, view_kwargs=view_kwargs)
