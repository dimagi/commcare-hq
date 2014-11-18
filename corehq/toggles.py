from functools import wraps
import hashlib
from django.http import Http404
import math
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


def deterministic_random(input_string):
    """
    Returns a deterministically random number between 0 and 1 based on the
    value of the string. The same input should always produce the same output.
    """
    return float.fromhex(hashlib.md5(input_string).hexdigest()) / math.pow(2, 128)


class PredicatablyRandomToggle(StaticToggle):
    """
    A toggle that is predictably random based off some axis. Useful for for doing
    a randomized rollout of a feature. E.g. "turn this on for 5% of domains", or
    "turn this on for 40% of users".

    It extends StaticToggle, so individual domains/users can also be explicitly added.
    """

    def __init__(self, slug, label, namespace, randomness):
        super(PredicatablyRandomToggle, self).__init__(slug, label, [namespace])
        assert namespace, 'namespace must be defined!'
        self.namespace = namespace
        assert 0 <= randomness <= 1, 'randomness must be between 0 and 1!'
        self.randomness = randomness

    @property
    def randomness_percent(self):
        return "{:.0f}".format(self.randomness * 100)

    def _get_identifier(self, item):
        return '{}:{}:{}'.format(self.namespace, self.slug, item)

    def enabled(self, item, **kwargs):
        return (
            (item and deterministic_random(self._get_identifier(item)) < self.randomness)
            or super(PredicatablyRandomToggle, self).enabled(item, **kwargs)
        )

# if no namespaces are specified the user namespace is assumed
NAMESPACE_USER = object()
NAMESPACE_DOMAIN = 'domain'


def all_toggles():
    """
    Loads all toggles
    """
    # trick for listing the attributes of the current module.
    # http://stackoverflow.com/a/990450/8207
    for toggle_name, toggle in globals().items():
        if not toggle_name.startswith('__'):
            if isinstance(toggle, StaticToggle):
                yield toggle


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

BOOTSTRAP3_PREVIEW = StaticToggle(
    'bootstrap3_preview',
    'Bootstrap 3 Preview',
    [NAMESPACE_USER]
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

IS_DEVELOPER = StaticToggle(
    'is_developer',
    'Is developer'
)

PATHWAYS_PREVIEW = StaticToggle(
    'pathways_preview',
    'Is Pathways preview'
)

MM_CASE_PROPERTIES = StaticToggle(
    'mm_case_properties',
    'Multimedia Case Properties',
)

VISIT_SCHEDULER = StaticToggle(
    'app_builder_visit_scheduler',
    'Visit Scheduler',
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

DASHBOARD_PREVIEW = StaticToggle(
    'dashboard_preview',
    'HQ Dashboard Preview'
)

EDIT_SUBMISSIONS = StaticToggle(
    'edit_submissions',
    'Submission Editing on HQ'
)

USER_CONFIGURABLE_REPORTS = StaticToggle(
    'user_reports',
    'User configurable reports UI',
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)


VIEW_SYNC_HISTORY = StaticToggle(
    'sync_history_report',
    'Enable sync history report'
)


STOCK_TRANSACTION_EXPORT = StaticToggle(
    'ledger_export',
    'Show "export transactions" link on case details page',
)


NEW_CASE_PROCESSING = PredicatablyRandomToggle(
    'new_case_processing',
    'Use new case processing/rebuild logic',
    namespace=NAMESPACE_DOMAIN,
    randomness=0.05,
)
