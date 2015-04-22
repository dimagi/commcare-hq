from functools import wraps
import hashlib
from django.http import Http404
import math
from toggle.shortcuts import toggle_enabled, set_toggle


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

    def set(self, item, enabled, namespace=None):
        set_toggle(self.slug, item, enabled, namespace)

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
        super(PredicatablyRandomToggle, self).__init__(slug, label, list(namespace))
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


def toggles_dict(username=None, domain=None):
    """
    Loads all toggles into a dictionary for use in JS
    """
    return {t.slug: True for t in all_toggles() if (t.enabled(username) or
                                                    t.enabled(domain))}


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

BOOTSTRAP3_PREVIEW = StaticToggle(
    'bootstrap3_preview',
    'Bootstrap 3 Preview',
    [NAMESPACE_USER]
)

CASE_LIST_CUSTOM_XML = StaticToggle(
    'case_list_custom_xml',
    'Show text area for entering custom case list xml',
)

CASE_LIST_TILE = StaticToggle(
    'case_list_tile',
    'Allow configuration of case list tiles',
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

DETAIL_LIST_TABS = StaticToggle(
    'detail-list-tabs',
    'Tabs in the case detail list',
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

GRAPH_CREATION = StaticToggle(
    'graph-creation',
    'Case list/detail graph creation',
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

OFFLINE_CLOUDCARE = StaticToggle(
    'offline-cloudcare',
    'Offline Cloudcare'
)

CASE_REBUILD = StaticToggle(
    'case_rebuild',
    'Show UI-based case and form rebuild options (primarily for support team)',
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

EDIT_SUBMISSIONS = StaticToggle(
    'edit_submissions',
    'Submission Editing on HQ',
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
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

SYNC_ALL_LOCATIONS = StaticToggle(
    'sync_all_locations',
    'Sync the full location hierarchy when syncing location fixtures',
    [NAMESPACE_DOMAIN]
)

NO_VELLUM = StaticToggle(
    'no_vellum',
    'Allow disabling Form Builder per form '
    '(for custom forms that Vellum breaks)',
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

DOUBLE_MANAGEMENT = StaticToggle(
    'double_management',
    'Case list actions a.k.a. double management',
    [NAMESPACE_USER, NAMESPACE_DOMAIN]
)

SPLIT_MULTISELECT_EXPORT = StaticToggle(
    'split_multiselect_export',
    'Split multiselect columns in custom exports',
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

CAN_EDIT_EULA = StaticToggle(
    'can_edit_eula',
    "Whether this user can set the custom eula and data sharing internal project options. "
    "This should be a small number of DIMAGI ONLY users",
)

STOCK_AND_RECEIPT_SMS_HANDLER = StaticToggle(
    'stock_and_sms_handler',
    "Enable the stock report handler to accept both stock and receipt values "
    "in the format 'soh abc 100.20'",
    [NAMESPACE_DOMAIN]
)

PAGINATE_WEB_USERS = StaticToggle(
    'paginate_web_users',
    'Paginate Web Users',
)

LOOSE_SYNC_TOKEN_VALIDATION = StaticToggle(
    'loose_sync_token_validation',
    "Don't fail hard on missing or deleted sync tokens.",
    [NAMESPACE_DOMAIN]
)

MULTIPLE_LOCATIONS_PER_USER = StaticToggle(
    'multiple_locations',
    "Enable multiple locations per user on domain.",
    [NAMESPACE_DOMAIN]
)

PRODUCTS_PER_LOCATION = StaticToggle(
    'products_per_location',
    "Products Per Location: Specify products stocked at individual locations.  "
    "This doesn't actually do anything yet.",
    [NAMESPACE_DOMAIN]
)

ALLOW_CASE_ATTACHMENTS_VIEW = StaticToggle(
    'allow_case_attachments_view',
    "Explicitly allow user to access case attachments, even if they can't view the case list report.",
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

LOCATION_TYPE_STOCK_RATES = StaticToggle(
    'location_type_stock_rates',
    "Specify stock rates per location type.",
    [NAMESPACE_DOMAIN]
)

BULK_ARCHIVE_FORMS = StaticToggle(
    'bulk_archive_forms',
    'Bulk archive forms with excel',
)

TRANSFER_DOMAIN = StaticToggle(
    'transfer_domain',
    'Transfer domains to different users',
    [NAMESPACE_DOMAIN]
)

DHIS2_DOMAIN = StaticToggle(
    'dhis2_domain',
    'Enable DHIS2 integration for this domain',
    [NAMESPACE_DOMAIN]
)

PRIME_RESTORE = StaticToggle(
    'prime_restore',
    'Prime restore cache',
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

FORM_LINK_WORKFLOW = StaticToggle(
    'form_link_workflow',
    'Form linking workflow available on forms',
    [NAMESPACE_DOMAIN],
)

# not referenced in code directly but passed through to vellum
# see toggles_dict
VELLUM_TRANSACTION_QUESTION_TYPES = StaticToggle(
    'transaction_question_types',
    "Adds transaction-related question types in the form builder",
    [NAMESPACE_DOMAIN]
)

VELLUM_ITEMSETS = StaticToggle(
    'itemsets',
    "Adds dynamic (itemset) select and multi-select question types to the "
    "form builder",
    [NAMESPACE_DOMAIN]
)

VELLUM_HELP_MARKDOWN = StaticToggle(
    'help_markdown',
    "Use markdown for the help text in the form builder",
    [NAMESPACE_DOMAIN]
)

VELLUM_SAVE_TO_CASE = StaticToggle(
    'save_to_case',
    "Adds save to case as a question to the form builder",
    [NAMESPACE_DOMAIN]
)

CACHE_AND_INDEX = StaticToggle(
    'cache_and_index',
    'Enable the "Cache and Index" format option when choosing sort properties '
    'in the app builder',
    [NAMESPACE_DOMAIN],
)

CUSTOM_PROPERTIES = StaticToggle(
    'custom_properties',
    'Allow users to add arbitrary custom properties to their appliation',
    [NAMESPACE_DOMAIN]
)

FILE_RESTORE = StaticToggle(
    'file_restore',
    'Use files to do phone restore',
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
)

GLOBAL_SMS_RATES = StaticToggle(
    'global_sms_rates',
    'Global SMS Rates page',
    [NAMESPACE_USER]
)

BULK_SMS_VERIFICATION = StaticToggle(
    'bulk_sms_verification',
    'Allow initiating the SMS phone verification workflow for all users in a group.',
    [NAMESPACE_USER, NAMESPACE_DOMAIN],
)

BULK_PAYMENTS = StaticToggle(
    'bulk_payments',
    'Enable payment of invoices by bulk credit payments and invoice generation for wire tranfers',
)

MODULE_FILTER = StaticToggle(
    'module_filter',
    'Enable module filtering',
    [NAMESPACE_DOMAIN],
)

USE_NEW_TIMEZONE_BEHAVIOR = StaticToggle(
    'use_new_timezone_behavior',
    ("Enable properly dealing with timezones in phone timestamps "
     "during submission and in reports. "
     "(Please do not set manually, "
     "because it has to be accompanied by a migration.)"),
    [NAMESPACE_DOMAIN],
)

USER_AS_A_CASE = StaticToggle(
    'user_as_a_case',
    'Enable "User-As-A-Case" to store user properties in a case and use them in forms',
    [NAMESPACE_DOMAIN]
)

STREAM_RESTORE_CACHE = StaticToggle(
    'stream_cached_restore',
    'Stream cached restore from couchdb',
    [NAMESPACE_DOMAIN]
)
