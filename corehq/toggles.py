from datetime import datetime
from collections import namedtuple
from functools import wraps
import hashlib
from django.http import Http404
import math

from django.contrib import messages
from django.conf import settings
from couchdbkit import ResourceNotFound
from django.urls import reverse
from django.utils.safestring import mark_safe
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
                 description=None, save_fn=None, always_enabled=None,
                 always_disabled=None, enabled_for_new_domains_after=None,
                 enabled_for_new_users_after=None):
        self.slug = slug
        self.label = label
        self.tag = tag
        self.help_link = help_link
        self.description = description
        # Optionally provide a callable to be called whenever the toggle is
        # updated.  This is only applicable to domain toggles.  It must accept
        # two parameters, `domain_name` and `toggle_is_enabled`
        self.save_fn = save_fn
        self.always_enabled = always_enabled or set()
        self.always_disabled = always_disabled or set()
        self.enabled_for_new_domains_after = enabled_for_new_domains_after
        self.enabled_for_new_users_after = enabled_for_new_users_after
        if namespaces:
            self.namespaces = [None if n == NAMESPACE_USER else n for n in namespaces]
        else:
            self.namespaces = [None]

    def enabled(self, item, namespace=Ellipsis):
        if item in self.always_enabled:
            return True
        elif item in self.always_disabled:
            return False

        if namespace is not Ellipsis and namespace not in self.namespaces:
            # short circuit if we're checking an item that isn't supported by this toggle
            return False

        domain_enabled_after = self.enabled_for_new_domains_after
        if (domain_enabled_after is not None and NAMESPACE_DOMAIN in self.namespaces
                and was_domain_created_after(item, domain_enabled_after)):
            return True

        user_enabled_after = self.enabled_for_new_users_after
        if (user_enabled_after is not None and was_user_created_after(item, user_enabled_after)):
            return True

        namespaces = self.namespaces if namespace is Ellipsis else [namespace]
        return any([toggle_enabled(self.slug, item, namespace=n) for n in namespaces])

    def enabled_for_request(self, request):
        return (
            None in self.namespaces
            and hasattr(request, 'user')
            and self.enabled(request.user.username, namespace=None)
        ) or (
            NAMESPACE_DOMAIN in self.namespaces
            and hasattr(request, 'domain')
            and self.enabled(request.domain, namespace=NAMESPACE_DOMAIN)
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
                    (hasattr(request, 'user') and self.enabled(request.user.username, namespace=None))
                    or (hasattr(request, 'domain') and self.enabled(request.domain, namespace=NAMESPACE_DOMAIN))
                ):
                    return view_func(request, *args, **kwargs)
                if request.user.is_superuser:
                    from corehq.apps.toggle_ui.views import ToggleEditView
                    toggle_url = reverse(ToggleEditView.urlname, args=[self.slug])
                    messages.warning(request, mark_safe((
                        'This <a href="{}">feature flag</a> should be enabled '
                        'to access this URL'
                    ).format(toggle_url)))
                raise Http404()
            return wrapped_view
        return decorator

    def get_enabled_domains(self):
        from toggle.models import Toggle
        try:
            toggle = Toggle.get(self.slug)
        except ResourceNotFound:
            return []

        enabled_users = toggle.enabled_users
        domains = {user.split('domain:')[1] for user in enabled_users if 'domain:' in user}
        domains |= self.always_enabled
        domains -= self.always_disabled
        return list(domains)


def was_domain_created_after(domain, checkpoint):
    """
    Return true if domain was created after checkpoint

    :param domain: Domain name (string).
    :param checkpoint: datetime object.
    """
    from corehq.apps.domain.models import Domain
    domain_obj = Domain.get_by_name(domain)
    return (
        domain_obj is not None and
        domain_obj.date_created is not None and
        domain_obj.date_created > checkpoint
    )


def was_user_created_after(username, checkpoint):
    """
    Return true if user was created after checkpoint

    :param username: Web User username (string).
    :param checkpoint: datetime object.
    """
    from corehq.apps.users.models import WebUser
    user = WebUser.get_by_username(username)
    return (
        user is not None and
        user.created_on is not None and
        user.created_on > checkpoint
    )


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
                                                      help_link=help_link, description=description,
                                                      always_disabled=always_disabled)
        assert namespaces, 'namespaces must be defined!'
        assert 0 <= randomness <= 1, 'randomness must be between 0 and 1!'
        self.randomness = randomness

    @property
    def randomness_percent(self):
        return "{:.0f}".format(self.randomness * 100)

    def _get_identifier(self, item):
        return '{}:{}:{}'.format(self.namespaces, self.slug, item)

    def enabled(self, item, **kwargs):
        if settings.UNIT_TESTING:
            return False
        elif item in self.always_disabled:
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
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
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
    help_link='https://confluence.dimagi.com/display/public/Custom+Case+XML+Overview',
    namespaces=[NAMESPACE_DOMAIN]
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

CASE_DETAIL_PRINT = StaticToggle(
    'case_detail_print',
    'Allowing printing of the case detail, based on an HTML template',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
)

DATA_FILE_DOWNLOAD = StaticToggle(
    'data_file_download',
    'Offer hosting and sharing data files for downloading, e.g. cleaned and anonymised form exports',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
    # TODO: Create Confluence docs and add help link
)


DETAIL_LIST_TAB_NODESETS = StaticToggle(
    'detail-list-tab-nodesets',
    'Associate a nodeset with a case detail tab',
    TAG_PRODUCT_PATH,
    help_link='https://confluence.dimagi.com/display/internal/Case+Detail+Nodesets',
    namespaces=[NAMESPACE_DOMAIN]
)

DHIS2_INTEGRATION = StaticToggle(
    'dhis2_integration',
    'DHIS2 Integration',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

GRAPH_CREATION = StaticToggle(
    'graph-creation',
    'Case list/detail graph creation',
    TAG_EXPERIMENTAL,
    help_link='https://confluence.dimagi.com/display/RD/Graphing+in+HQ',
    namespaces=[NAMESPACE_DOMAIN]
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
    help_link='https://confluence.dimagi.com/display/internal/Multimedia+Case+Properties+Feature+Flag',
    namespaces=[NAMESPACE_DOMAIN, NAMESPACE_USER]
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
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
    description=(
        "A feature which will allow your domain to create User Configurable Reports."
    ),
    help_link='https://confluence.dimagi.com/display/RD/User+Configurable+Reporting',
)

EXPORT_NO_SORT = StaticToggle(
    'export_no_sort',
    'Do not sort exports',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
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

SYNC_ALL_LOCATIONS = StaticToggle(
    'sync_all_locations',
    '(Deprecated) Sync the full location hierarchy when syncing location fixtures',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
    description="Do not turn this feature flag. It is only used for providing compatability for old projects. "
    "We are actively trying to remove projects from this list. This functionality is now possible by using the "
    "Advanced Settings on the Organization Levels page and setting the Level to Expand From option."
)

HIERARCHICAL_LOCATION_FIXTURE = StaticToggle(
    'hierarchical_location_fixture',
    'Display Settings To Get Hierarchical Location Fixture',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
    description=(
        "Do not turn this feature flag.  It is only used for providing "
        "compatability for old projects.  We are actively trying to remove "
        "projects from this list."
    ),
)

EXTENSION_CASES_SYNC_ENABLED = StaticToggle(
    'extension_sync',
    'Enable extension syncing',
    TAG_EXPERIMENTAL,
    help_link='https://confluence.dimagi.com/display/ccinternal/Extension+Cases',
    namespaces=[NAMESPACE_DOMAIN],
    always_enabled={'enikshay'},
)


ROLE_WEBAPPS_PERMISSIONS = StaticToggle(
    'role_webapps_permissions',
    'Toggle which webapps to see based on role',
    TAG_PRODUCT_PATH,
    namespaces=[NAMESPACE_DOMAIN],
)


SYNC_SEARCH_CASE_CLAIM = StaticToggle(
    'search_claim',
    'Enable synchronous mobile searching and case claiming',
    TAG_PRODUCT_PATH,
    help_link='https://confluence.dimagi.com/display/internal/Remote+Case+Search+and+Claim',
    namespaces=[NAMESPACE_DOMAIN]
)

LIVEQUERY_SYNC = StaticToggle(
    'livequery_sync',
    'Enable livequery sync algorithm',
    TAG_PRODUCT_PATH,
    namespaces=[NAMESPACE_DOMAIN]
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

# This toggle offers the "multiple_apps_unlimited" mobile flag to non-Dimagi users
MOBILE_PRIVILEGES_FLAG = StaticToggle(
    'mobile_privileges_flag',
    'Offer "Enable Privileges on Mobile" flag.',
    TAG_EXPERIMENTAL,
    [NAMESPACE_USER]
)

PRODUCTS_PER_LOCATION = StaticToggle(
    'products_per_location',
    "Products Per Location: Specify products stocked at individual locations.  "
    "This doesn't actually do anything yet.",
    TAG_ONE_OFF,
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
    help_link='https://confluence.dimagi.com/display/ccinternal/Printing+from+a+form+in+CommCare+Android',
    namespaces=[NAMESPACE_DOMAIN]
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
    help_link='https://confluence.dimagi.com/display/internal/CommCare+Android+Developer+Options',
    namespaces=[NAMESPACE_DOMAIN]
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
    always_enabled={'icds-cas'}
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

CUSTOM_INSTANCES = StaticToggle(
    'custom_instances',
    'Inject custom instance declarations',
    TAG_EXPERIMENTAL,
    namespaces=[NAMESPACE_USER, NAMESPACE_DOMAIN],
)

APPLICATION_ERROR_REPORT = StaticToggle(
    'application_error_report',
    'Show Application Error Report',
    TAG_EXPERIMENTAL,
    help_link='https://confluence.dimagi.com/display/internal/Show+Application+Error+Report+Feature+Flag',
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

DASHBOARD_ICDS_REPORT = StaticToggle(
    'dashboard_icds_reports',
    'Enable access to the dashboard reports for ICDS',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

NINETYNINE_DOTS = StaticToggle(
    '99dots_integration',
    'Enable access to 99DOTS',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

ENIKSHAY_API = StaticToggle(
    'enikshay_api',
    'Enable access to eNikshay api endpoints',
    TAG_ONE_OFF,
    [NAMESPACE_USER],
    always_enabled={"enikshay"},
)

NIKSHAY_INTEGRATION = StaticToggle(
    'nikshay_integration',
    'Enable patient registration in Nikshay',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

BETS_INTEGRATION = StaticToggle(
    'bets_repeaters',
    'Enable BETS data forwarders',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
    always_enabled={"enikshay"},
)

OPENMRS_INTEGRATION = StaticToggle(
    'openmrs_integration',
    'Enable OpenMRS integration',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
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
    help_link='https://confluence.dimagi.com/display/ccinternal/Support+Flag',
)

BASIC_CHILD_MODULE = StaticToggle(
    'child_module',
    'Basic modules can be child modules',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

FORMPLAYER_USE_LIVEQUERY = StaticToggle(
    'formplayer_use_livequery',
    'Use LiveQuery on Web Apps',
    TAG_ONE_OFF,
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
    help_link='https://confluence.dimagi.com/display/commcarepublic/SMS+Self+Registration',
    namespaces=[NAMESPACE_DOMAIN],
)

MESSAGE_LOG_METADATA = StaticToggle(
    'message_log_metadata',
    'Include message id in Message Log export.',
    TAG_ONE_OFF,
    [NAMESPACE_USER],
)

ABT_REMINDER_RECIPIENT = StaticToggle(
    'abt_reminder_recipient',
    "Custom reminder recipients",
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
    'Allow specifying a custom base URL for an application. Main use case is '
    'to allow migrating ICDS to a new cluster.',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)


PHONE_NUMBERS_REPORT = StaticToggle(
    'phone_numbers_report',
    "Shows information related to the phone numbers owned by a project's contacts",
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)


INBOUND_SMS_LENIENCY = StaticToggle(
    'inbound_sms_leniency',
    "Inbound SMS leniency on domain-owned gateways. "
    "WARNING: This wil be rolled out slowly; do not enable on your own.",
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
    help_link='https://confluence.dimagi.com/display/internal/Demo+Mobile+Workers',
    namespaces=[NAMESPACE_DOMAIN]
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

APP_MANAGER_V1 = StaticToggle(
    'app_manager_v1',
    'Turn OFF prototype for case management onboarding (App Manager V2)',
    TAG_ONE_OFF,
    [NAMESPACE_USER]
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
    'Make the Worker Activity Report use the Groups or Users or Locations (LocationRestrictedEMWF) filter',
    TAG_ONE_OFF,
    namespaces=[NAMESPACE_DOMAIN],
    description=(
        "This flag allows you filter the users to display in the same way as the "
        "other reports - by individual user, group, or location.  Note that this "
        "will also force the report to always display by user."
    ),
)

ENIKSHAY = StaticToggle(
    'enikshay',
    "Enable custom enikshay functionality: additional user and location validation",
    TAG_ONE_OFF,
    namespaces=[NAMESPACE_DOMAIN],
    always_enabled={'enikshay'},
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

LOCATION_USERS = StaticToggle(
    'location_users',
    'Autogenerate users for each location',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
    description=(
        "This flag adds an option to the location types page (under 'advanced "
        "mode') to create users for all locations of a specified type."
    ),
)

SORT_CALCULATION_IN_CASE_LIST = StaticToggle(
    'sort_calculation_in_case_list',
    'Configure a custom xpath calculation for Sort Property in Case Lists',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

ANONYMOUS_WEB_APPS_USAGE = StaticToggle(
    'anonymous_web_apps_usage',
    'Allow anonymous users to access web apps applications',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN],
    always_disabled={'icds-cas'}
)

INCLUDE_METADATA_IN_UCR_EXCEL_EXPORTS = StaticToggle(
    'include_metadata_in_ucr_excel_exports',
    'Include metadata in UCR excel exports',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

UATBC_ADHERENCE_TASK = StaticToggle(
    'uatbc_adherence_calculations',
    'This runs backend adherence calculations for enikshay domains',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

VIEW_APP_CHANGES = StaticToggle(
    'app-changes-with-improved-diff',
    'Improved app changes view',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
)

COUCH_SQL_MIGRATION_BLACKLIST = StaticToggle(
    'couch_sql_migration_blacklist',
    "Domains to exclude from migrating to SQL backend. Includes the folling"
    "by default: 'ews-ghana', 'ils-gateway', 'ils-gateway-train'",
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN],
    always_enabled={
        'ews-ghana', 'ils-gateway', 'ils-gateway-train'
    }
)

PAGINATED_EXPORTS = StaticToggle(
    'paginated_exports',
    'Allows for pagination of exports for very large exports',
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN]
)

LOGIN_AS_ALWAYS_OFF = StaticToggle(
    'always_turn_login_as_off',
    'Always turn login as off',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

BLOBDB_RESTORE = PredictablyRandomToggle(
    'blobdb_restore',
    "Blobdb restore",
    TAG_PRODUCT_PATH,
    [NAMESPACE_DOMAIN],
    randomness=1.0,
)

SHOW_DEV_TOGGLE_INFO = StaticToggle(
    'highlight_feature_flags',
    'Highlight / Mark Feature Flags in the UI',
    TAG_ONE_OFF,
    [NAMESPACE_USER]
)

DASHBOARD_GRAPHS = StaticToggle(
    'dashboard_graphs',
    'Show submission graph on dashboard',
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

PUBLISH_CUSTOM_REPORTS = StaticToggle(
    'publish_custom_reports',
    "Publish custom reports (No needed Authorization)",
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

MOTECH = StaticToggle(
    'motech',
    "Show Motech tab",
    TAG_EXPERIMENTAL,
    [NAMESPACE_DOMAIN]
)

DISPLAY_CONDITION_ON_TABS = StaticToggle(
    'display_condition_on_nodeset',
    'Show Display Condition on Case Detail Tabs',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

PHONE_HEARTBEAT = StaticToggle(
    'phone_apk_heartbeat',
    'Expose phone apk heartbeat URL and add it profile.xml',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

SKIP_REMOVE_INDICES = StaticToggle(
    'skip_remove_indices',
    'Make _remove_indices_from_deleted_cases_task into a no-op.',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)

PREVENT_MOBILE_UCR_SYNC = StaticToggle(
    'prevent_mobile_ucr_sync',
    'Used for ICDS emergencies when UCR sync is killing the DB',
    TAG_ONE_OFF,
    [NAMESPACE_DOMAIN]
)
