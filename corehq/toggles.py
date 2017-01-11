from collections import namedtuple
from functools import wraps
import hashlib
from django.http import Http404
import math
from corehq.util.quickcache import quickcache
from toggle.shortcuts import toggle_enabled, set_toggle

Tag = namedtuple('Tag', 'name css_class description')
TAG_ONE_OFF = Tag(
    name='One-Off',
    css_class='danger',
    description="This feature flag was created for one specific use-case. "
    "Please don't enable it for your project without first talking to the tech "
    "team. This is not fully supported and may break other features.",
)
TAG_EXPERIMENTAL = Tag(
    name='Experimental',
    css_class='warning',
    description="This feature flag is a proof-of-concept that we're currently "
    "testing out. It may be changed before it is released or it may be dropped.",
)
TAG_PRODUCT_PATH = Tag(
    name='Product Path',
    css_class='info',
    description="We intend to release this feature.  It may still be in QA or "
    "we may have a few changes to make before it's ready for general use.",
)
TAG_PRODUCT_CORE = Tag(
    name='Core Product',
    css_class='success',
    description="This is a core-product feature that you should feel free to "
    "use.  We've feature-flagged it probably because it is an advanced "
    "workflow we'd like more control over.",
)
TAG_PREVIEW = Tag(
    name='Preview',
    css_class='default',
    description="",  # I'm not sure...
)
ALL_TAGS = [TAG_ONE_OFF, TAG_EXPERIMENTAL, TAG_PRODUCT_PATH, TAG_PRODUCT_CORE, TAG_PREVIEW]


class StaticToggle(object):

    def __init__(self, slug, label, tag, namespaces=None, help_link=None,
                 description=None, save_fn=None):
        self.slug = slug
        self.label = label
        self.tag = tag
        self.help_link = help_link
        self.description = description
        # Optionally provide a callable to be called whenever the toggle is
        # updated.  This is only applicable to domain toggles.  It must accept
        # two parameters, `domain_name` and `toggle_is_enabled`
        self.save_fn = save_fn
        if namespaces:
            self.namespaces = [None if n == NAMESPACE_USER else n for n in namespaces]
        else:
            self.namespaces = [None]

    def enabled(self, item, **kwargs):
        return any([toggle_enabled(self.slug, item, namespace=n, **kwargs) for n in self.namespaces])

    def enabled_for_request(self, request):
        return (
            None in self.namespaces
            and hasattr(request, 'user')
            and toggle_enabled(self.slug, request.user.username, None)
        ) or (
            NAMESPACE_DOMAIN in self.namespaces
            and hasattr(request, 'domain')
            and toggle_enabled(self.slug, request.domain, NAMESPACE_DOMAIN)
        )

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
    if isinstance(input_string, unicode):
        input_string = input_string.encode('utf-8')
    return float.fromhex(hashlib.md5(input_string).hexdigest()) / math.pow(2, 128)


class PredictablyRandomToggle(StaticToggle):
    """
    A toggle that is predictably random based off some axis. Useful for for doing
    a randomized rollout of a feature. E.g. "turn this on for 5% of domains", or
    "turn this on for 40% of users".

    It extends StaticToggle, so individual domains/users can also be explicitly added.
    """

    def __init__(self,
            slug,
            label,
            tag,
            namespaces,
            randomness,
            help_link=None,
            description=None,
            always_disabled=None):
        super(PredictablyRandomToggle, self).__init__(slug, label, tag, list(namespaces),
                                                      help_link=help_link, description=description)
        assert namespaces, 'namespaces must be defined!'
        assert 0 <= randomness <= 1, 'randomness must be between 0 and 1!'
        self.randomness = randomness
        self.always_disabled = always_disabled or []

    @property
    def randomness_percent(self):
        return "{:.0f}".format(self.randomness * 100)

    def _get_identifier(self, item):
        return '{}:{}:{}'.format(self.namespaces, self.slug, item)

    def enabled(self, item, **kwargs):
        if item in self.always_disabled:
            return False
        return (
            (item and deterministic_random(self._get_identifier(item)) < self.randomness)
            or super(PredictablyRandomToggle, self).enabled(item, **kwargs)
        )

# if no namespaces are specified the user namespace is assumed
NAMESPACE_USER = 'user'
NAMESPACE_DOMAIN = 'domain'
ALL_NAMESPACES = [NAMESPACE_USER, NAMESPACE_DOMAIN]


def any_toggle_enabled(*toggles):
    """
    Return a view decorator for allowing access if any of the given toggles are
    enabled. Example usage:

    @toggles.any_toggle_enabled(REPORT_BUILDER, USER_CONFIGURABLE_REPORTS)
    def delete_custom_report():
        pass

    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            for t in toggles:
                if t.enabled_for_request(request):
                    return view_func(request, *args, **kwargs)
            raise Http404()
        return wrapped_view
    return decorator


@quickcache([])
def all_toggles():
    """
    Loads all toggles
    """
    return all_toggles_by_name_in_scope(globals()).values()


def all_toggles_by_name():
    # trick for listing the attributes of the current module.
    # http://stackoverflow.com/a/990450/8207
    return all_toggles_by_name_in_scope(globals())


def all_toggles_by_name_in_scope(scope_dict):
    result = {}
    for toggle_name, toggle in scope_dict.items():
        if not toggle_name.startswith('__'):
            if isinstance(toggle, StaticToggle):
                result[toggle_name] = toggle
    return result


def toggles_dict(username=None, domain=None):
    """
    Loads all toggles into a dictionary for use in JS

    (only enabled toggles are included)
    """
    return {t.slug: True for t in all_toggles() if (t.enabled(username) or
                                                    t.enabled(domain))}


def toggle_values_by_name(username=None, domain=None):
    """
    Loads all toggles into a dictionary for use in JS

    all toggles (including those not enabled) are included
    """
    return {toggle_name: (toggle.enabled(username) or toggle.enabled(domain))
            for toggle_name, toggle in all_toggles_by_name().items()}


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
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
)

APP_BUILDER_SHADOW_MODULES = StaticToggle(
    'shadow-app-builder',
    'Shadow Modules',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/internal/Shadow+Modules',
)

CASE_LIST_CUSTOM_XML = StaticToggle(
    'case_list_custom_xml',
    'Show text area for entering custom case list xml',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

CASE_LIST_CUSTOM_VARIABLES = StaticToggle(
    'case_list_custom_variables',
    'Show text area for entering custom variables',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

CASE_LIST_TILE = StaticToggle(
    'case_list_tile',
    'Allow configuration of case list tiles',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

SHOW_PERSIST_CASE_CONTEXT_SETTING = StaticToggle(
    'show_persist_case_context_setting',
    'Allow toggling the persistent case context tile',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
)

CASE_LIST_LOOKUP = StaticToggle(
    'case_list_lookup',
    'Allow external android callouts to search the caselist',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

ADD_USERS_FROM_LOCATION = StaticToggle(
    'add_users_from_location',
    "Allow users to add new mobile workers from the locations page",
    TAG_PRODUCT_CORE,
    [NAMESPACE_DOMAIN]
)

DETAIL_LIST_TABS = StaticToggle(
    'detail-list-tabs',
    'Tabs in the case detail list',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

DETAIL_LIST_TAB_NODESETS = StaticToggle(
    'detail-list-tab-nodesets',
    'Associate a nodeset with a case detail tab',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/internal/Case+Detail+Nodesets',
)

GRAPH_CREATION = StaticToggle(
    'graph-creation',
    'Case list/detail graph creation',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

IS_DEVELOPER = StaticToggle(
    'is_developer',
    'Is developer',
    TAG_EXPERIMENTAL
)

MM_CASE_PROPERTIES = StaticToggle(
    'mm_case_properties',
    'Multimedia Case Properties',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

VISIT_SCHEDULER = StaticToggle(
    'app_builder_visit_scheduler',
    'Visit Scheduler',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)


USER_CONFIGURABLE_REPORTS = StaticToggle(
    'user_reports',
    'User configurable reports UI',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

LOCATIONS_IN_UCR = StaticToggle(
    'locations_in_ucr',
    'Add Locations as one of the Source Types for User Configurable Reports',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

REPORT_BUILDER = StaticToggle(
    'report_builder',
    'Report Builder',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

ASYNC_RESTORE = StaticToggle(
    'async_restore',
    'Generate restore response in an asynchronous task to prevent timeouts',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
)

REPORT_BUILDER_BETA_GROUP = StaticToggle(
    'report_builder_beta_group',
    'RB beta group',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
)

STOCK_TRANSACTION_EXPORT = StaticToggle(
    'ledger_export',
    'Show "export transactions" link on case details page',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

SYNC_ALL_LOCATIONS = StaticToggle(
    'sync_all_locations',
    'Sync the full location hierarchy when syncing location fixtures',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

FLAT_LOCATION_FIXTURE = StaticToggle(
    'flat_location_fixture',
    'Sync the location fixture in a flat format.',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

EXTENSION_CASES_SYNC_ENABLED = StaticToggle(
    'extension_sync',
    'Enable extension syncing',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

SYNC_SEARCH_CASE_CLAIM = StaticToggle(
    'search_claim',
    'Enable synchronous mobile searching and case claiming',
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

HIPAA_COMPLIANCE_CHECKBOX = StaticToggle(
    'hipaa_compliance_checkbox',
    'Show HIPAA compliance checkbox',
    TAG_ONE_OFF,
    [NAMESPACE_USER],
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

LOOSE_SYNC_TOKEN_VALIDATION = StaticToggle(
    'loose_sync_token_validation',
    "Don't fail hard on missing or deleted sync tokens.",
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

# This toggle offers the "multiple_apps_unlimited" mobile flag to non-Dimagi users
MOBILE_PRIVILEGES_FLAG = StaticToggle(
    'mobile_privileges_flag',
    'Offer "Enable Privileges on Mobile" flag.',
    TAG_EXPERIMENTAL,
    [NAMESPACE_USER]
)

MULTIPLE_LOCATIONS_PER_USER = StaticToggle(
    'multiple_locations',
    "(Deprecated) Enable multiple locations per user on domain.",
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
    description="Don't enable this flag."
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

VELLUM_SAVE_TO_CASE = StaticToggle(
    'save_to_case',
    "Adds save to case as a question to the form builder",
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

VELLUM_PRINTING = StaticToggle(
    'printing',
    "Enables the Print Android App Callout",
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

VELLUM_DATA_IN_SETVALUE = StaticToggle(
    'allow_data_reference_in_setvalue',
    "Allow data references in a setvalue",
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

CACHE_AND_INDEX = StaticToggle(
    'cache_and_index',
    'Enable the "Cache and Index" format option when choosing sort properties '
    'in the app builder',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
)

CUSTOM_PROPERTIES = StaticToggle(
    'custom_properties',
    'Allow users to add arbitrary custom properties to their application',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

ENABLE_LOADTEST_USERS = StaticToggle(
    'enable_loadtest_users',
    'Enable creating loadtest users on HQ',
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/internal/Loadtest+Users',
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
    "(Deprecated) Allow project to restrict web user permissions by location",
    TAG_ONE_OFF,
    namespaces=[NAMESPACE_DOMAIN],
    description="Don't enable this flag."
)

API_THROTTLE_WHITELIST = StaticToggle(
    'api_throttle_whitelist',
    ('API throttle whitelist'),
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_USER],
)

API_BLACKLIST = StaticToggle(
    'API_BLACKLIST',
    ("Blacklist API access to a user or domain that spams us"),
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_DOMAIN, NAMESPACE_USER],
    description="For temporary, emergency use only. If a partner doesn't properly "
    "throttle their API requests, it can hammer our infrastructure, causing "
    "outages. This will cut off the tide, but we should communicate with them "
    "immediately.",
)

FORM_SUBMISSION_BLACKLIST = StaticToggle(
    'FORM_SUBMISSION_BLACKLIST',
    ("Blacklist form submissions from a domain that spams us"),
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_DOMAIN],
    description="This is a temporary solution to an unusually high volume of "
    "form submissions from a domain.  We have some projects that automatically "
    "send forms. If that ever causes problems, we can use this to cut them off.",
)


def _commtrackify(domain_name, toggle_is_enabled):
    from corehq.apps.domain.models import Domain
    domain = Domain.get_by_name(domain_name, strict=True)
    if domain and domain.commtrack_enabled != toggle_is_enabled:
        if toggle_is_enabled:
            domain.convert_to_commtrack()
        else:
            domain.commtrack_enabled = False
            domain.save()


COMMTRACK = StaticToggle(
    'commtrack',
    "CommCare Supply",
    TAG_PRODUCT_CORE,
    description=(
        '<a href="http://www.commtrack.org/home/">CommCare Supply</a> '
        "is a logistics and supply chain management module. It is designed "
        "to improve the management, transport, and resupply of a variety of "
        "goods and materials, from medication to food to bednets. <br/>"
    ),
    help_link='https://help.commcarehq.org/display/commtrack/CommTrack+Home',
    namespaces=[NAMESPACE_DOMAIN],
    save_fn=_commtrackify,
)

INSTANCE_VIEWER = StaticToggle(
    'instance_viewer',
    'CloudCare Form Debugging Tool',
    TAG_PRODUCT_PATH,
    namespaces=[NAMESPACE_USER, NAMESPACE_DOMAIN],
)

CUSTOM_INSTANCES = StaticToggle(
    'custom_instances',
    'Inject custom instance declarations',
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_USER, NAMESPACE_DOMAIN],
)

LOCATIONS_IN_REPORTS = StaticToggle(
    'LOCATIONS_IN_REPORTS',
    "Include locations in report filters",
    TAG_PRODUCT_PATH,
    namespaces=[NAMESPACE_DOMAIN],
)

CLOUDCARE_CACHE = StaticToggle(
    'cloudcare_cache',
    'Aggresively cache case list, can result in stale data',
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_DOMAIN],
)

APPLICATION_ERROR_REPORT = StaticToggle(
    'application_error_report',
    'Show Application Error Report',
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_USER],
)

OPENCLINICA = StaticToggle(
    'openclinica',
    'Offer OpenClinica settings and CDISC ODM export',
    TAG_ONE_OFF,
    namespaces=[NAMESPACE_DOMAIN],
)

CUSTOM_MENU_BAR = StaticToggle(
    'custom_menu_bar',
    "Hide Dashboard and Applications from top menu bar "
    "for non-admin users",
    TAG_ONE_OFF,
    namespaces=[NAMESPACE_DOMAIN],
)

ICDS_REPORTS = StaticToggle(
    'icds_reports',
    'Enable access to the Tableau dashboard for ICDS',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

NINETYNINE_DOTS = StaticToggle(
    '99dots_integration',
    'Enable access to 99DOTS',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

NIKSHAY_INTEGRATION = StaticToggle(
    'nikshay_integration',
    'Enable patient registration in Nikshay',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

MULTIPLE_CHOICE_CUSTOM_FIELD = StaticToggle(
    'multiple_choice_custom_field',
    'Allow project to use multiple choice field in custom fields',
    TAG_PRODUCT_PATH,
    namespaces=[NAMESPACE_DOMAIN]
)

RESTRICT_FORM_EDIT_BY_LOCATION = StaticToggle(
    'restrict_form_edit_by_location',
    "(Deprecated) Restrict ability to edit/archive forms by the web user's location",
    TAG_ONE_OFF,
    namespaces=[NAMESPACE_DOMAIN],
    description="Don't enable this flag."
)

SUPPORT = StaticToggle(
    'support',
    'General toggle for support features',
    TAG_EXPERIMENTAL,
)

BASIC_CHILD_MODULE = StaticToggle(
    'child_module',
    'Basic modules can be child modules',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

HSPH_HACK = StaticToggle(
    'hsph_hack',
    'Optmization hack for HSPH',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
)

USE_FORMPLAYER_FRONTEND = StaticToggle(
    'use_formplayer_frontend',
    'Use New CloudCare',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
)

FIXTURE_CASE_SELECTION = StaticToggle(
    'fixture_case',
    'Allow a configurable case list that is filtered based on a fixture type and fixture selection (Due List)',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
)

EWS_INVALID_REPORT_RESPONSE = StaticToggle(
    'ews_invalid_report_response',
    'Send response about invalid stock on hand',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)


BROADCAST_TO_LOCATIONS = StaticToggle(
    'broadcast_to_locations',
    'Send broadcasts to locations',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
)

MOBILE_WORKER_SELF_REGISTRATION = StaticToggle(
    'mobile_worker_self_registration',
    'Allow mobile workers to self register',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
)

MESSAGE_LOG_METADATA = StaticToggle(
    'message_log_metadata',
    'Include message id in Message Log export.',
    TAG_ONE_OFF,
    [NAMESPACE_USER],
)

ABT_REMINDER_RECIPIENT = StaticToggle(
    'abt_reminder_recipient',
    "Ability to send a reminder to the case owner's location's parent location",
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
)

AUTO_CASE_UPDATE_ENHANCEMENTS = StaticToggle(
    'auto_case_updates',
    'Enable enhancements to the Auto Case Update feature.',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
)

RUN_AUTO_CASE_UPDATES_ON_SAVE = StaticToggle(
    'run_auto_case_updates_on_save',
    'Run Auto Case Update rules on each case save.',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
)

EWS_BROADCAST_BY_ROLE = StaticToggle(
    'ews_broadcast_by_role',
    'EWS: Filter broadcast recipients by role',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
)

SMS_PERFORMANCE_FEEDBACK = StaticToggle(
    'sms_performance_feedback',
    'Enable SMS-based performance feedback',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
    help_link='https://docs.google.com/document/d/1YvbYLV4auuf8gVdYZ6jFZTsOLfJdxm49XhvWkska4GE/edit#',
)

LEGACY_SYNC_SUPPORT = StaticToggle(
    'legacy_sync_support',
    "Support mobile sync bugs in older projects (2.9 and below).",
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

VIEW_BUILD_SOURCE = StaticToggle(
    'diff_builds',
    'Allow users to view and diff build source files',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

EWS_WEB_USER_EXTENSION = StaticToggle(
    'ews_web_user_extension',
    'Enable EWSGhana web user extension',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

CALL_CENTER_LOCATION_OWNERS = StaticToggle(
    'call_center_location_owners',
    'Enable the use of locations as owners of call center cases',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

GRID_MENUS = StaticToggle(
    'grid_menus',
    'Allow using grid menus on Android',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/internal/Grid+Views',
)

OLD_EXPORTS = StaticToggle(
    'old_exports',
    'Use old backend export infrastructure',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

TF_DOES_NOT_USE_SQLITE_BACKEND = StaticToggle(
    'not_tf_sql_backend',
    'Domains that do not use a SQLite backend for Touchforms',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
)

CUSTOM_APP_BASE_URL = StaticToggle(
    'custom_app_base_url',
    'Allow specifying a custom base URL for an application. Main use case is to allow migrating ICDS to a new cluster.',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)


PROJECT_HEALTH_DASHBOARD = StaticToggle(
    'project_health_dashboard',
    'Shows the project performance dashboard in the reports navigation',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)


UNLIMITED_REPORT_BUILDER_REPORTS = StaticToggle(
    'unlimited_report_builder_reports',
    'Allow unlimited reports created in report builder',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

MOBILE_USER_DEMO_MODE = StaticToggle(
    'mobile_user_demo_mode',
    'Ability to make a mobile worker into Demo only mobile worker',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)


EXPORT_ZIPPED_APPS = StaticToggle(
    'export-zipped-apps',
    'Export+Import Zipped Applications',
    TAG_EXPERIMENTAL,
    [NAMESPACE_USER]
)


SEND_UCR_REBUILD_INFO = StaticToggle(
    'send_ucr_rebuild_info',
    'Notify when UCR rebuilds finish or error.',
    TAG_EXPERIMENTAL,
    [NAMESPACE_USER]
)

EMG_AND_REC_SMS_HANDLERS = StaticToggle(
    'emg_and_rec_sms_handlers',
    'Enable emergency and receipt sms handlers used in ILSGateway',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

ALLOW_USER_DEFINED_EXPORT_COLUMNS = StaticToggle(
    'allow_user_defined_export_columns',
    'Allows users to specify their own export columns',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
)


CUSTOM_CALENDAR_FIXTURE = StaticToggle(
    'custom_calendar_fixture',
    'Send a calendar fixture down to all users (R&D)',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
)


PREVIEW_APP = StaticToggle(
    'preview_app',
    'Preview an application in the app builder',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
)

DISABLE_COLUMN_LIMIT_IN_UCR = StaticToggle(
    'disable_column_limit_in_ucr',
    'Disable column limit in UCR',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

CLOUDCARE_LATEST_BUILD = StaticToggle(
    'use_latest_build_cloudcare',
    'Uses latest build for cloudcare instead of latest starred',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

APP_MANAGER_V2 = StaticToggle(
    'app_manager_v2',
    'Prototype for case management onboarding (App Manager V2)',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

SHOW_PREVIEW_APP_SETTINGS = StaticToggle(
    'preview_app_settings',
    'Show preview app settings button',
    TAG_PRODUCT_CORE,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

USER_TESTING_SIMPLIFY = StaticToggle(
    'user_testing_simplify',
    'Simplify the UI for user testing experiments',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

DATA_MIGRATION = StaticToggle(
    'data_migration',
    'Disable submissions and restores during a data migration',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

EMWF_WORKER_ACTIVITY_REPORT = StaticToggle(
    'emwf_worker_activity_report',
    'Make the Worker Activity Report use the Groups or Users (EMWF) filter',
    TAG_ONE_OFF,
    namespaces=[NAMESPACE_DOMAIN],
    description=(
        "This flag allows you filter the users to display in the same way as the "
        "other reports - by individual user, group, or location.  Note that this "
        "will also force the report to always display by user."
    ),
)

DATA_DICTIONARY = StaticToggle(
    'data_dictionary',
    'Domain level data dictionary of cases',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

LINKED_APPS = StaticToggle(
    'linked_apps',
    'Allows master and linked apps',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

NIMBUS_FORM_VALIDATION = PredictablyRandomToggle(
    'nimbus_form_validation',
    'Use Nimbus to validate XForms',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
    randomness=1.0
)

COPY_CASE_CONFIGS = StaticToggle(
    'copy_case_configs',
    'Allow copying case list / details screens in basic modules.',
    TAG_PRODUCT_CORE,
    [NAMESPACE_DOMAIN]
)
