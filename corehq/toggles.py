from functools import wraps
from django.http import Http404
from toggle.shortcuts import toggle_enabled

class StaticToggle(object):
    def __init__(self, slug, label, namespaces=None):
        self.slug = slug
        self.label = label
        if namespaces:
            self.namespaces = [None if n == NAMESPACE_USER else n for n in namespaces]
        else:
            self.namespaces = [None]

    def enabled(self, item, **kwargs):
        return any([toggle_enabled(self.slug, item, namespace=n, **kwargs) for n in self.namespaces])

    def required_decorator(self):
        """
        Returns a view function decorator that checks to see if the domain
        or user in the request has the appropriate toggle enabled.
        """
        def decorator(view_func):
            @wraps(view_func)
            def wrapped_view(request, *args, **kwargs):
                if (
                    (hasattr(request, 'user') and self.enabled(request.user.username))
                    or (hasattr(request, 'domain') and self.enabled(request.domain))
                ):
                    return view_func(request, *args, **kwargs)
                raise Http404()
            return wrapped_view
        return decorator


# if no namespaces are specified the user namespace is assumed
NAMESPACE_USER = object()
NAMESPACE_DOMAIN = 'domain'

APP_BUILDER_CUSTOM_PARENT_REF = StaticToggle(
    'custom-parent-ref',
    'Custom case parent reference'
)

APP_BUILDER_CAREPLAN = StaticToggle(
    'careplan',
    'Careplan module'
)

APP_BUILDER_ADVANCED = StaticToggle(
    'advanced-app-builder',
    'Advanced Module in App-Builder'
)

APP_BUILDER_INCLUDE_MULTIMEDIA_ODK = StaticToggle(
    'include-multimedia-odk',
    'Include multimedia in ODK deploy'
)

PRBAC_DEMO = StaticToggle(
    'prbacdemo',
    'Roles and permissions'
)

ACCOUNTING_PREVIEW = StaticToggle(
    'accounting_preview',
    'Accounting preview',
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

INVOICE_TRIGGER = StaticToggle(
    'invoice_trigger',
    'Accounting Trigger Invoices',
    [NAMESPACE_USER]
)

OFFLINE_CLOUDCARE = StaticToggle(
    'offline-cloudcare',
    'Offline Cloudcare'
)

REMINDERS_UI_PREVIEW = StaticToggle(
    'reminders_ui_preview',
    'New reminders UI'
)

CASE_REBUILD = StaticToggle(
    'case_rebuild',
    'Show UI-based case rebuild option',
)

ANDROID_OFFLINE_INSTALL = StaticToggle(
    'android_offline_install',
    'Android Offline Install',
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
)

IS_DEVELOPER = StaticToggle(
    'is_developer',
    'Is developer'
)

CUSTOM_PRODUCT_DATA = StaticToggle(
    'custom_product_data',
    'Custom Product Data',
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

MM_CASE_PROPERTIES = StaticToggle(
    'mm_case_properties',
    'Multimedia Case Properties',
)
