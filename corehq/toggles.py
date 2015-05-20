from collections import namedtuple
from functools import wraps
import hashlib
from django.http import Http404
import math
from toggle.shortcuts import toggle_enabled, set_toggle

Tag = namedtuple('Tag', 'name css_class')
TAG_ONE_OFF = Tag(name='One-Off', css_class='important')
TAG_EXPERIMENTAL = Tag(name='Experimental', css_class='warning')
TAG_PRODUCT_PATH = Tag(name='Product Path', css_class='info')
TAG_PRODUCT_CORE = Tag(name='Core Product', css_class='success')
TAG_PREVIEW = Tag(name='Preview', css_class='default')
TAG_UNKNOWN = Tag(name='Unknown', css_class='inverse')
ALL_TAGS = [TAG_ONE_OFF, TAG_EXPERIMENTAL, TAG_PRODUCT_PATH, TAG_PRODUCT_CORE, TAG_PREVIEW, TAG_UNKNOWN]


class StaticToggle(object):
    def __init__(self, slug, label, tag, namespaces=None, help_link=None, description=None):
        self.slug = slug
        self.label = label
        self.tag = tag
        self.help_link = help_link
        self.description = description
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


class PredictablyRandomToggle(StaticToggle):
    """
    A toggle that is predictably random based off some axis. Useful for for doing
    a randomized rollout of a feature. E.g. "turn this on for 5% of domains", or
    "turn this on for 40% of users".

    It extends StaticToggle, so individual domains/users can also be explicitly added.
    """

    def __init__(self, slug, label, tag, namespaces, randomness, help_link=None, description=None):
        super(PredictablyRandomToggle, self).__init__(slug, label, tag, list(namespaces),
                                                      help_link=help_link, description=description)
        assert namespaces, 'namespaces must be defined!'
        assert 0 <= randomness <= 1, 'randomness must be between 0 and 1!'
        self.randomness = randomness

    @property
    def randomness_percent(self):
        return "{:.0f}".format(self.randomness * 100)

    def _get_identifier(self, item):
        return '{}:{}:{}'.format(self.namespaces, self.slug, item)

    def enabled(self, item, **kwargs):
        return (
            (item and deterministic_random(self._get_identifier(item)) < self.randomness)
            or super(PredictablyRandomToggle, self).enabled(item, **kwargs)
        )

# if no namespaces are specified the user namespace is assumed
NAMESPACE_USER = 'user'
NAMESPACE_DOMAIN = 'domain'
ALL_NAMESPACES = [NAMESPACE_USER, NAMESPACE_DOMAIN]


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
    'Custom case parent reference',
    TAG_ONE_OFF
)

APP_BUILDER_CAREPLAN = StaticToggle(
    'careplan',
    'Careplan module',
    TAG_EXPERIMENTAL
)

APP_BUILDER_ADVANCED = StaticToggle(
    'advanced-app-builder',
    'Advanced Module in App-Builder',
    TAG_EXPERIMENTAL
)

APP_BUILDER_INCLUDE_MULTIMEDIA_ODK = StaticToggle(
    'include-multimedia-odk',
    'Include multimedia in ODK deploy',
    TAG_ONE_OFF
)

BOOTSTRAP3_PREVIEW = StaticToggle(
    'bootstrap3_preview',
    'Bootstrap 3 Preview',
    TAG_PRODUCT_PATH,
    [NAMESPACE_USER]
)

CASE_LIST_CUSTOM_XML = StaticToggle(
    'case_list_custom_xml',
    'Show text area for entering custom case list xml',
    TAG_EXPERIMENTAL,
)

CASE_LIST_TILE = StaticToggle(
    'case_list_tile',
    'Allow configuration of case list tiles',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

DETAIL_LIST_TABS = StaticToggle(
    'detail-list-tabs',
    'Tabs in the case detail list',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

GRAPH_CREATION = StaticToggle(
    'graph-creation',
    'Case list/detail graph creation',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

OFFLINE_CLOUDCARE = StaticToggle(
    'offline-cloudcare',
    'Offline Cloudcare',
    TAG_EXPERIMENTAL
)

CASE_REBUILD = StaticToggle(
    'case_rebuild',
    'Show UI-based case and form rebuild options (primarily for support team)',
    TAG_EXPERIMENTAL
)

IS_DEVELOPER = StaticToggle(
    'is_developer',
    'Is developer',
    TAG_EXPERIMENTAL
)

PATHWAYS_PREVIEW = StaticToggle(
    'pathways_preview',
    'Is Pathways preview',
    TAG_ONE_OFF
)

MM_CASE_PROPERTIES = StaticToggle(
    'mm_case_properties',
    'Multimedia Case Properties',
    TAG_PRODUCT_PATH
)

VISIT_SCHEDULER = StaticToggle(
    'app_builder_visit_scheduler',
    'Visit Scheduler',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

EDIT_SUBMISSIONS = StaticToggle(
    'edit_submissions',
    'Submission Editing on HQ',
    TAG_PRODUCT_CORE,
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
)

USER_CONFIGURABLE_REPORTS = StaticToggle(
    'user_reports',
    'User configurable reports UI',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

STOCK_TRANSACTION_EXPORT = StaticToggle(
    'ledger_export',
    'Show "export transactions" link on case details page',
    TAG_PRODUCT_PATH
)

SYNC_ALL_LOCATIONS = StaticToggle(
    'sync_all_locations',
    'Sync the full location hierarchy when syncing location fixtures',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

NO_VELLUM = StaticToggle(
    'no_vellum',
    'Allow disabling Form Builder per form '
    '(for custom forms that Vellum breaks)',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

CAN_EDIT_EULA = StaticToggle(
    'can_edit_eula',
    "Whether this user can set the custom eula and data sharing internal project options. "
    "This should be a small number of DIMAGI ONLY users",
    TAG_EXPERIMENTAL,
)

STOCK_AND_RECEIPT_SMS_HANDLER = StaticToggle(
    'stock_and_sms_handler',
    "Enable the stock report handler to accept both stock and receipt values "
    "in the format 'soh abc 100.20'",
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

PAGINATE_WEB_USERS = StaticToggle(
    'paginate_web_users',
    'Paginate Web Users',
    TAG_PRODUCT_PATH
)

LOOSE_SYNC_TOKEN_VALIDATION = StaticToggle(
    'loose_sync_token_validation',
    "Don't fail hard on missing or deleted sync tokens.",
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

MULTIPLE_LOCATIONS_PER_USER = StaticToggle(
    'multiple_locations',
    "Enable multiple locations per user on domain.",
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

PRODUCTS_PER_LOCATION = StaticToggle(
    'products_per_location',
    "Products Per Location: Specify products stocked at individual locations.  "
    "This doesn't actually do anything yet.",
    TAG_PRODUCT_CORE,
    [NAMESPACE_DOMAIN]
)

ALLOW_CASE_ATTACHMENTS_VIEW = StaticToggle(
    'allow_case_attachments_view',
    "Explicitly allow user to access case attachments, even if they can't view the case list report.",
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

LOCATION_TYPE_STOCK_RATES = StaticToggle(
    'location_type_stock_rates',
    "Specify stock rates per location type.",
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

BULK_ARCHIVE_FORMS = StaticToggle(
    'bulk_archive_forms',
    'Bulk archive forms with excel',
    TAG_PRODUCT_PATH
)

TRANSFER_DOMAIN = StaticToggle(
    'transfer_domain',
    'Transfer domains to different users',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

DHIS2_DOMAIN = StaticToggle(
    'dhis2_domain',
    'Enable DHIS2 integration for this domain',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

PRIME_RESTORE = StaticToggle(
    'prime_restore',
    'Prime restore cache',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

FORM_LINK_WORKFLOW = StaticToggle(
    'form_link_workflow',
    'Form linking workflow available on forms',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
)

# not referenced in code directly but passed through to vellum
# see toggles_dict
VELLUM_TRANSACTION_QUESTION_TYPES = StaticToggle(
    'transaction_question_types',
    "Adds transaction-related question types in the form builder",
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

VELLUM_HELP_MARKDOWN = StaticToggle(
    'help_markdown',
    "Use markdown for the help text in the form builder",
    TAG_UNKNOWN,
    [NAMESPACE_DOMAIN]
)

VELLUM_SAVE_TO_CASE = StaticToggle(
    'save_to_case',
    "Adds save to case as a question to the form builder",
    TAG_UNKNOWN,
    [NAMESPACE_DOMAIN]
)

VELLUM_ADVANCED_ITEMSETS = StaticToggle(
    'advanced_itemsets',
    "Allows a user to configure itemsets for more than lookup tables",
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

CACHE_AND_INDEX = StaticToggle(
    'cache_and_index',
    'Enable the "Cache and Index" format option when choosing sort properties '
    'in the app builder',
    TAG_UNKNOWN,
    [NAMESPACE_DOMAIN],
)

CUSTOM_PROPERTIES = StaticToggle(
    'custom_properties',
    'Allow users to add arbitrary custom properties to their application',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

FILE_RESTORE = PredictablyRandomToggle(
    'file_restore',
    'Use files to do phone restore',
    TAG_PRODUCT_PATH,
    randomness=.5,
    namespaces=[NAMESPACE_DOMAIN, NAMESPACE_USER],
)

BULK_SMS_VERIFICATION = StaticToggle(
    'bulk_sms_verification',
    'Allow initiating the SMS phone verification workflow for all users in a group.',
    TAG_ONE_OFF,
    [NAMESPACE_USER, NAMESPACE_DOMAIN],
)

USE_NEW_TIMEZONE_BEHAVIOR = StaticToggle(
    'use_new_timezone_behavior',
    ("Enable properly dealing with timezones in phone timestamps "
     "during submission and in reports. "
     "(Please do not set manually, "
     "because it has to be accompanied by a migration.)"),
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
)

USER_AS_A_CASE = StaticToggle(
    'user_as_a_case',
    'Enable "User-As-A-Case" to store user properties in a case and use them in forms',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

STREAM_RESTORE_CACHE = PredictablyRandomToggle(
    'stream_cached_restore',
    'Stream cached restore from couchdb',
    TAG_EXPERIMENTAL,
    randomness=.5,
    namespaces=[NAMESPACE_DOMAIN]
)

ENABLE_LOADTEST_USERS = StaticToggle(
    'enable_loadtest_users',
    'Enable creating loadtest users on HQ',
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/ccinternal/Loadtest+Users',
)

OWNERSHIP_CLEANLINESS = PredictablyRandomToggle(
    'enable_owner_cleanliness_flags',
    'Enable tracking ownership cleanliness on submission',
    TAG_EXPERIMENTAL,
    randomness=.05,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://docs.google.com/a/dimagi.com/document/d/12WfZLerFL832LZbMwqRAvXt82scdjDL51WZVNa31f28/edit#heading=h.gu9sjekp0u2p',
)

MOBILE_UCR = StaticToggle(
    'mobile_ucr',
    ('Mobile UCR: Configure viewing user configurable reports on the mobile '
     'through the app builder'),
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_DOMAIN],
)

RESTRICT_WEB_USERS_BY_LOCATION = StaticToggle(
    'restrict_web_users_by_location',
    "Allow project to restrict web user permissions by location",
    TAG_PRODUCT_CORE,
    namespaces=[NAMESPACE_DOMAIN],
)

FM_FACING_SUBSCRIPTIONS = StaticToggle(
    'fm_facing_subscriptions',
    'FM Facing Subscription Management Interface',
    TAG_PRODUCT_CORE,
)

API_THROTTLE_WHITELIST = StaticToggle(
    'api_throttle_whitelist',
    ('API throttle whitelist'),
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_USER],
)
