from collections import namedtuple
from functools import wraps
import hashlib
import math

from django.contrib import messages
from django.conf import settings
from django.http import Http404
from django.urls import reverse
from django.utils.safestring import mark_safe

from couchdbkit import ResourceNotFound
from corehq.util.quickcache import quickcache
from toggle.shortcuts import toggle_enabled, set_toggle

Tag = namedtuple('Tag', 'name css_class description')
TAG_CUSTOM = Tag(
    name='One-Off / Custom',
    css_class='warning',
    description="This feature flag was created for one specific project. "
    "Please don't enable it for any other projects. "
    "This is NOT SUPPORTED outside of that project and may break other features.",
)
TAG_DEPRECATED = Tag(
    name='Deprecated',
    css_class='danger',
    description="This feature flag is being removed. "
    "Do not add any new projects to this list.",
)
TAG_PRODUCT = Tag(
    name='Product',
    css_class='success',
    description="This is a core-product feature that you should feel free to "
    "use.  We've feature-flagged until release.",
)
TAG_PREVIEW = Tag(
    name='Preview',
    css_class='default',
    description='',
)
TAG_SOLUTIONS = Tag(
    name='Solutions',
    css_class='info',
    description="These features are only available for our services projects. This may affect support and "
    "pricing when the project is transitioned to a subscription."
)
TAG_INTERNAL = Tag(
    name='Internal Engineering Tools',
    css_class='default',
    description="These are tools for our engineering team to use to manage the product",
)
ALL_TAGS = [TAG_CUSTOM, TAG_DEPRECATED, TAG_PRODUCT, TAG_SOLUTIONS, TAG_INTERNAL]


class StaticToggle(object):

    def __init__(self, slug, label, tag, namespaces=None, help_link=None,
                 description=None, save_fn=None, always_enabled=None,
                 always_disabled=None, enabled_for_new_domains_after=None,
                 enabled_for_new_users_after=None, relevant_environments=None):
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
        # pass in a set of environments where this toggle applies
        self.relevant_environments = relevant_environments
        if namespaces:
            self.namespaces = [None if n == NAMESPACE_USER else n for n in namespaces]
        else:
            self.namespaces = [None]

    def enabled(self, item, namespace=Ellipsis):
        if self.relevant_environments and not (
            settings.SERVER_ENVIRONMENT in self.relevant_environments
            or settings.DEBUG
        ):
            # Don't even bother looking it up in the cache
            return False
        if item in self.always_enabled:
            return True
        elif item in self.always_disabled:
            return False

        if namespace == NAMESPACE_USER:
            namespace = None  # because:
            #     __init__() ... self.namespaces = [None if n == NAMESPACE_USER else n for n in namespaces]
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

    def __init__(
        self,
        slug,
        label,
        tag,
        namespaces,
        randomness,
        help_link=None,
        description=None,
        always_disabled=None
    ):
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

    def enabled(self, item, namespace=Ellipsis):
        if namespace == NAMESPACE_USER:
            namespace = None  # because:
            # StaticToggle.__init__(): self.namespaces = [None if n == NAMESPACE_USER else n for n in namespaces]

        all_namespaces = {None if n == NAMESPACE_USER else n for n in ALL_NAMESPACES}
        if namespace is Ellipsis and set(self.namespaces) != all_namespaces:
            raise ValueError(
                'PredictablyRandomToggle.enabled() cannot be determined for toggle "{slug}" because it is not '
                'available for all namespaces and the namespace of "{item}" is not given.'.format(
                    slug=self.slug,
                    item=item,
                )
            )

        if settings.UNIT_TESTING:
            return False
        elif item in self.always_disabled:
            return False
        elif namespace is not Ellipsis and namespace not in self.namespaces:
            return False
        return (
            (item and deterministic_random(self._get_identifier(item)) < self.randomness)
            or super(PredictablyRandomToggle, self).enabled(item, namespace)
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
    return {t.slug: True for t in all_toggles() if (t.enabled(username, NAMESPACE_USER) or
                                                    t.enabled(domain, NAMESPACE_DOMAIN))}


def toggle_values_by_name(username=None, domain=None):
    """
    Loads all toggles into a dictionary for use in JS

    all toggles (including those not enabled) are included
    """
    return {toggle_name: (toggle.enabled(username, NAMESPACE_USER) or
                          toggle.enabled(domain, NAMESPACE_DOMAIN))
            for toggle_name, toggle in all_toggles_by_name().items()}


APP_BUILDER_CUSTOM_PARENT_REF = StaticToggle(
    'custom-parent-ref',
    'ICDS: Custom case parent reference',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

APP_BUILDER_ADVANCED = StaticToggle(
    'advanced-app-builder',
    'Advanced Module in App-Builder',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    description="Advanced Modules allow you to autoload and manage multiple case types, "
                "but may behave in unexpected ways.",
    help_link='https://confluence.dimagi.com/display/ccinternal/Advanced+Modules',
)

APP_BUILDER_SHADOW_MODULES = StaticToggle(
    'shadow-app-builder',
    'Shadow Modules',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/ccinternal/Shadow+Modules',
)

CASE_LIST_CUSTOM_XML = StaticToggle(
    'case_list_custom_xml',
    'Show text area for entering custom case list xml',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/public/Custom+Case+XML+Overview',
)

CASE_LIST_CUSTOM_VARIABLES = StaticToggle(
    'case_list_custom_variables',
    'Show text area for entering custom variables',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    description='Defines custom variables that can be used in case list or detail calculations',
)

CASE_LIST_TILE = StaticToggle(
    'case_list_tile',
    'Allow configuration of case list tiles',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

SHOW_PERSIST_CASE_CONTEXT_SETTING = StaticToggle(
    'show_persist_case_context_setting',
    'Allow toggling the persistent case context tile',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
)

CASE_LIST_LOOKUP = StaticToggle(
    'case_list_lookup',
    'Allow external android callouts to search the caselist',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

ADD_USERS_FROM_LOCATION = StaticToggle(
    'add_users_from_location',
    "Allow users to add new mobile workers from the locations page",
    TAG_PRODUCT,
    [NAMESPACE_DOMAIN]
)

CASE_DETAIL_PRINT = StaticToggle(
    'case_detail_print',
    'MLabour: Allowing printing of the case detail, based on an HTML template',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

DATA_FILE_DOWNLOAD = StaticToggle(
    'data_file_download',
    'UW: Offer hosting and sharing data files for downloading, e.g. cleaned and anonymised form exports',
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN],
    # TODO: Create Confluence docs and add help link
)


DETAIL_LIST_TAB_NODESETS = StaticToggle(
    'detail-list-tab-nodesets',
    'Associate a nodeset with a case detail tab',
    TAG_SOLUTIONS,
    help_link='https://confluence.dimagi.com/display/ccinternal/Case+Detail+Nodesets',
    namespaces=[NAMESPACE_DOMAIN]
)

DHIS2_INTEGRATION = StaticToggle(
    'dhis2_integration',
    'DHIS2 Integration',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN]
)

GRAPH_CREATION = StaticToggle(
    'graph-creation',
    'Case list/detail graph creation',
    TAG_SOLUTIONS,
    help_link='https://confluence.dimagi.com/display/RD/Graphing+in+HQ',
    namespaces=[NAMESPACE_DOMAIN]
)

IS_DEVELOPER = StaticToggle(
    'is_developer',
    'Is developer',
    TAG_INTERNAL,
    description="Used to give non super-users access to select super-user features"
)

MM_CASE_PROPERTIES = StaticToggle(
    'mm_case_properties',
    'Multimedia Case Properties',
    TAG_DEPRECATED,
    help_link='https://confluence.dimagi.com/display/ccinternal/Multimedia+Case+Properties+Feature+Flag',
    namespaces=[NAMESPACE_DOMAIN, NAMESPACE_USER]
)

VISIT_SCHEDULER = StaticToggle(
    'app_builder_visit_scheduler',
    'ICDS: Visit Scheduler',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)


USER_CONFIGURABLE_REPORTS = StaticToggle(
    'user_reports',
    'User configurable reports UI',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
    description=(
        "A feature which will allow your domain to create User Configurable Reports."
    ),
    help_link='https://confluence.dimagi.com/display/RD/User+Configurable+Reporting',
)

EXPORT_NO_SORT = StaticToggle(
    'export_no_sort',
    'Do not sort exports',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

LOCATIONS_IN_UCR = StaticToggle(
    'locations_in_ucr',
    'ICDS: Add Locations as one of the Source Types for User Configurable Reports',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

REPORT_BUILDER = StaticToggle(
    'report_builder',
    'Activate Report Builder for a project without setting up a subscription.',
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN],
)

REPORT_BUILDER_V1 = StaticToggle(
    "report_builder_v1",
    "Report builder V1",
    TAG_PRODUCT,
    [NAMESPACE_DOMAIN],
    description=(
        'Enables the old report builder. Note that the project must already have access to report builder.'
    )
)

ASYNC_RESTORE = StaticToggle(
    'async_restore',
    'Generate restore response in an asynchronous task to prevent timeouts',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
)

REPORT_BUILDER_BETA_GROUP = StaticToggle(
    'report_builder_beta_group',
    'RB beta group',
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN],
)

SYNC_ALL_LOCATIONS = StaticToggle(
    'sync_all_locations',
    '(Deprecated) Sync the full location hierarchy when syncing location fixtures',
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN],
    description="Do not turn this feature flag. It is only used for providing compatability for old projects. "
    "We are actively trying to remove projects from this list. This functionality is now possible by using the "
    "Advanced Settings on the Organization Levels page and setting the Level to Expand From option."
)

HIERARCHICAL_LOCATION_FIXTURE = StaticToggle(
    'hierarchical_location_fixture',
    'Display Settings To Get Hierarchical Location Fixture',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
    description=(
        "Do not turn this feature flag.  It is only used for providing "
        "compatability for old projects.  We are actively trying to remove "
        "projects from this list."
    ),
)

EXTENSION_CASES_SYNC_ENABLED = StaticToggle(
    'extension_sync',
    'Enikshay/L10K: Enable extension syncing',
    TAG_CUSTOM,
    help_link='https://confluence.dimagi.com/display/ccinternal/Extension+Cases',
    namespaces=[NAMESPACE_DOMAIN],
    always_enabled={'enikshay'},
)


ROLE_WEBAPPS_PERMISSIONS = StaticToggle(
    'role_webapps_permissions',
    'Enikshay/ICDS: Toggle which webapps to see based on role',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)


SYNC_SEARCH_CASE_CLAIM = StaticToggle(
    'search_claim',
    'Enable synchronous mobile searching and case claiming',
    TAG_SOLUTIONS,
    help_link='https://confluence.dimagi.com/display/ccinternal/Remote+Case+Search+and+Claim',
    namespaces=[NAMESPACE_DOMAIN]
)

LIVEQUERY_SYNC = StaticToggle(
    'livequery_sync',
    'Enable livequery sync algorithm',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN]
)

NO_VELLUM = StaticToggle(
    'no_vellum',
    'Allow disabling Form Builder per form '
    '(for custom forms that Vellum breaks)',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

HIPAA_COMPLIANCE_CHECKBOX = StaticToggle(
    'hipaa_compliance_checkbox',
    'Show HIPAA compliance checkbox',
    TAG_INTERNAL,
    [NAMESPACE_USER],
)

CAN_EDIT_EULA = StaticToggle(
    'can_edit_eula',
    "Whether this user can set the custom eula and data sharing internal project options. "
    "This should be a small number of DIMAGI ONLY users",
    TAG_INTERNAL,
)

STOCK_AND_RECEIPT_SMS_HANDLER = StaticToggle(
    'stock_and_sms_handler',
    "Enable the stock report handler to accept both stock and receipt values "
    "in the format 'soh abc 100.20'",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

# This toggle offers the "multiple_apps_unlimited" mobile flag to non-Dimagi users
MOBILE_PRIVILEGES_FLAG = StaticToggle(
    'mobile_privileges_flag',
    'Offer "Enable Privileges on Mobile" flag.',
    TAG_SOLUTIONS,
    [NAMESPACE_USER]
)

PRODUCTS_PER_LOCATION = StaticToggle(
    'products_per_location',
    "Products Per Location: Specify products stocked at individual locations.  "
    "This doesn't actually do anything yet.",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

ALLOW_CASE_ATTACHMENTS_VIEW = StaticToggle(
    'allow_case_attachments_view',
    "Explicitly allow user to access case attachments, even if they can't view the case list report.",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

LOCATION_TYPE_STOCK_RATES = StaticToggle(
    'location_type_stock_rates',
    "Specify stock rates per location type.",
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN]
)

BULK_ARCHIVE_FORMS = StaticToggle(
    'bulk_archive_forms',
    'Bulk archive forms with Excel',
    TAG_SOLUTIONS
)

TRANSFER_DOMAIN = StaticToggle(
    'transfer_domain',
    'Transfer domains to different users',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN]
)


FORM_LINK_WORKFLOW = StaticToggle(
    'form_link_workflow',
    'Form linking workflow available on forms',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
)

# not referenced in code directly but passed through to vellum
# see toggles_dict

VELLUM_SAVE_TO_CASE = StaticToggle(
    'save_to_case',
    "Adds save to case as a question to the form builder",
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    description='This flag allows case management inside repeat groups',
    help_link='https://confluence.dimagi.com/display/ccinternal/Save+to+Case+Feature+Flag',
)

VELLUM_PRINTING = StaticToggle(
    'printing',
    "Enables the Print Android App Callout",
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    description='Allows printing from CommCare on the device',
    help_link='https://confluence.dimagi.com/display/ccinternal/Printing+from+a+form+in+CommCare+Android',
)

VELLUM_DATA_IN_SETVALUE = StaticToggle(
    'allow_data_reference_in_setvalue',
    "Allow data references in a setvalue",
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    description="This allows referencing other questions in the form in a setvalue. "
                "This may still cause issues if the other questions have not been calculated yet",
)

CACHE_AND_INDEX = StaticToggle(
    'cache_and_index',
    'Enikshay/REC: Enable the "Cache and Index" format option when choosing sort properties '
    'in the app builder',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

CUSTOM_PROPERTIES = StaticToggle(
    'custom_properties',
    'Allow users to add arbitrary custom properties to their application',
    TAG_SOLUTIONS,
    help_link='https://confluence.dimagi.com/display/internal/CommCare+Android+Developer+Options+--+Internal#'
              'CommCareAndroidDeveloperOptions--Internal-SettingtheValueofaDeveloperOptionfromHQ',
    namespaces=[NAMESPACE_DOMAIN]
)

ENABLE_LOADTEST_USERS = StaticToggle(
    'enable_loadtest_users',
    'Enable creating loadtest users on HQ',
    TAG_SOLUTIONS,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/ccinternal/Loadtest+Users',
)

MOBILE_UCR = StaticToggle(
    'mobile_ucr',
    ('Mobile UCR: Configure viewing user configurable reports on the mobile '
     'through the app builder'),
    TAG_SOLUTIONS,
    namespaces=[NAMESPACE_DOMAIN],
    always_enabled={'icds-cas'}
)

RESTRICT_WEB_USERS_BY_LOCATION = StaticToggle(
    'restrict_web_users_by_location',
    "(Deprecated) Allow project to restrict web user permissions by location",
    TAG_DEPRECATED,
    namespaces=[NAMESPACE_DOMAIN],
    description="Don't enable this flag."
)

API_THROTTLE_WHITELIST = StaticToggle(
    'api_throttle_whitelist',
    ('API throttle whitelist'),
    TAG_INTERNAL,
    namespaces=[NAMESPACE_USER],
)

API_BLACKLIST = StaticToggle(
    'API_BLACKLIST',
    ("Blacklist API access to a user or domain that spams us"),
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN, NAMESPACE_USER],
    description="For temporary, emergency use only. If a partner doesn't properly "
    "throttle their API requests, it can hammer our infrastructure, causing "
    "outages. This will cut off the tide, but we should communicate with them "
    "immediately.",
)

FORM_SUBMISSION_BLACKLIST = StaticToggle(
    'FORM_SUBMISSION_BLACKLIST',
    ("Blacklist form submissions from a domain that spams us"),
    TAG_INTERNAL,
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
    TAG_SOLUTIONS,
    description=(
        '<a href="https://help.commcarehq.org/display/commtrack/CommCare+Supply+Home">CommCare Supply</a> '
        "is a logistics and supply chain management module. It is designed "
        "to improve the management, transport, and resupply of a variety of "
        "goods and materials, from medication to food to bednets. <br/>"
    ),
    help_link='https://help.commcarehq.org/display/commtrack/CommCare+Supply+Home',
    namespaces=[NAMESPACE_DOMAIN],
    save_fn=_commtrackify,
)

NON_COMMTRACK_LEDGERS = StaticToggle(
    'non_commtrack_ledgers',
    "Enikshay: Enable ledgers for projects not using Supply.",
    TAG_CUSTOM,
    description=(
        'Turns on the ledger fixture and ledger transaction question types in '
        'the form builder. ONLY WORKS ON SQL DOMAINS!'
    ),
    namespaces=[NAMESPACE_DOMAIN],
)

CUSTOM_INSTANCES = StaticToggle(
    'custom_instances',
    'Enikshay: Inject custom instance declarations',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER, NAMESPACE_DOMAIN],
)

APPLICATION_ERROR_REPORT = StaticToggle(
    'application_error_report',
    'Show Application Error Report',
    TAG_SOLUTIONS,
    help_link='https://confluence.dimagi.com/display/ccinternal/Show+Application+Error+Report+Feature+Flag',
    namespaces=[NAMESPACE_USER],
)

OPENCLINICA = StaticToggle(
    'openclinica',
    'KEMRI: Offer OpenClinica settings and CDISC ODM export',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

CUSTOM_MENU_BAR = StaticToggle(
    'custom_menu_bar',
    "Hide Dashboard and Applications from top menu bar "
    "for non-admin users",
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

ICDS_REPORTS = StaticToggle(
    'icds_reports',
    'Enable access to the Tableau dashboard for ICDS',
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN]
)

DASHBOARD_ICDS_REPORT = StaticToggle(
    'dashboard_icds_reports',
    'ICDS: Enable access to the dashboard reports for ICDS',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

NINETYNINE_DOTS = StaticToggle(
    '99dots_integration',
    'Enikshay: Enable access to 99DOTS',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

ENIKSHAY_API = StaticToggle(
    'enikshay_api',
    'Enikshay: Enable access to eNikshay api endpoints',
    TAG_CUSTOM,
    [NAMESPACE_USER],
    always_enabled={"enikshay"},
)

NIKSHAY_INTEGRATION = StaticToggle(
    'nikshay_integration',
    'Enikshay: Enable patient registration in Nikshay',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

BETS_INTEGRATION = StaticToggle(
    'bets_repeaters',
    'Enikshay: Enable BETS data forwarders',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    always_enabled={"enikshay"},
)

OPENMRS_INTEGRATION = StaticToggle(
    'openmrs_integration',
    'FGH: Enable OpenMRS integration',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

INDEX_LOCATION_DATA_DESCRIPTION = """
Add an option to the location fields page allowing you to specify fields which
should be indexed by the phone. This can provide a performance boost in
applications dealing with large location fixtures when using those fields for
filtering. The indexed fields will be made available as top level children of
the <location/> node with the prefix 'data_', and you must reference that to
take advantage of the optimization. For example, reference a field called
'is_test' like:
    instance('locations')/locations/location[data_is_test='1']
"""
INDEX_LOCATION_DATA = StaticToggle(
    'index_location_data',
    'Enikshay: Add option to index custom location fields',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    description=INDEX_LOCATION_DATA_DESCRIPTION,
)

MULTIPLE_CHOICE_CUSTOM_FIELD = StaticToggle(
    'multiple_choice_custom_field',
    'EWS: Allow project to use multiple choice field in custom fields',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description='This flag allows multiple choice fields in custom user data, location data and product data',
)

RESTRICT_FORM_EDIT_BY_LOCATION = StaticToggle(
    'restrict_form_edit_by_location',
    "(Deprecated) Restrict ability to edit/archive forms by the web user's location",
    TAG_DEPRECATED,
    namespaces=[NAMESPACE_DOMAIN],
    description="Don't enable this flag."
)

SUPPORT = StaticToggle(
    'support',
    'General toggle for support features',
    TAG_INTERNAL,
    help_link='https://confluence.dimagi.com/display/ccinternal/Support+Flag',
)

BASIC_CHILD_MODULE = StaticToggle(
    'child_module',
    'Basic modules can be child modules',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN]
)

FORMPLAYER_USE_LIVEQUERY = StaticToggle(
    'formplayer_use_livequery',
    'Use LiveQuery on Web Apps',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
)

FIXTURE_CASE_SELECTION = StaticToggle(
    'fixture_case',
    'ICDS: Allow a configurable case list that is filtered based on a fixture type and '
    'fixture selection (Due List)',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

EWS_INVALID_REPORT_RESPONSE = StaticToggle(
    'ews_invalid_report_response',
    'EWS: Send response about invalid stock on hand',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

BROADCAST_TO_LOCATIONS = StaticToggle(
    'broadcast_to_locations',
    'Send broadcasts to locations',
    TAG_PRODUCT,
    [NAMESPACE_DOMAIN],
)

MOBILE_WORKER_SELF_REGISTRATION = StaticToggle(
    'mobile_worker_self_registration',
    'Allow mobile workers to self register',
    TAG_SOLUTIONS,
    help_link='https://confluence.dimagi.com/display/commcarepublic/SMS+Self+Registration',
    namespaces=[NAMESPACE_DOMAIN],
)

MESSAGE_LOG_METADATA = StaticToggle(
    'message_log_metadata',
    'Include message id in Message Log export.',
    TAG_CUSTOM,
    [NAMESPACE_USER],
)

ABT_REMINDER_RECIPIENT = StaticToggle(
    'abt_reminder_recipient',
    "ABT: Custom reminder recipients",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

AUTO_CASE_UPDATE_ENHANCEMENTS = StaticToggle(
    'auto_case_updates',
    'Enable enhancements to the Auto Case Update feature.',
    TAG_PRODUCT,
    [NAMESPACE_DOMAIN],
)

RUN_AUTO_CASE_UPDATES_ON_SAVE = StaticToggle(
    'run_auto_case_updates_on_save',
    'Run Auto Case Update rules on each case save.',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
)

EWS_BROADCAST_BY_ROLE = StaticToggle(
    'ews_broadcast_by_role',
    'EWS: Filter broadcast recipients by role',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

SMS_PERFORMANCE_FEEDBACK = StaticToggle(
    'sms_performance_feedback',
    'Enable SMS-based performance feedback',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    help_link='https://docs.google.com/document/d/1YvbYLV4auuf8gVdYZ6jFZTsOLfJdxm49XhvWkska4GE/edit#',
)

LEGACY_SYNC_SUPPORT = StaticToggle(
    'legacy_sync_support',
    "Support mobile sync bugs in older projects (2.9 and below).",
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN]
)

EWS_WEB_USER_EXTENSION = StaticToggle(
    'ews_web_user_extension',
    'EWS: Enable EWSGhana web user extension',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

CALL_CENTER_LOCATION_OWNERS = StaticToggle(
    'call_center_location_owners',
    'ICDS: Enable the use of locations as owners of call center cases',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

OLD_EXPORTS = StaticToggle(
    'old_exports',
    'Use old backend export infrastructure',
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN]
)

TF_DOES_NOT_USE_SQLITE_BACKEND = StaticToggle(
    'not_tf_sql_backend',
    'Domains that do not use a SQLite backend for Touchforms',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
)

CUSTOM_APP_BASE_URL = StaticToggle(
    'custom_app_base_url',
    'ICDS/eNikshay: Allow specifying a custom base URL for an application. Main use case is '
    'to allow migrating ICDS to a new cluster.',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)


PHONE_NUMBERS_REPORT = StaticToggle(
    'phone_numbers_report',
    "Report related to the phone numbers owned by a project's contacts",
    TAG_PRODUCT,
    [NAMESPACE_DOMAIN]
)


INBOUND_SMS_LENIENCY = StaticToggle(
    'inbound_sms_leniency',
    "Inbound SMS leniency on domain-owned gateways. "
    "WARNING: This wil be rolled out slowly; do not enable on your own.",
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN]
)


UNLIMITED_REPORT_BUILDER_REPORTS = StaticToggle(
    'unlimited_report_builder_reports',
    'Allow unlimited reports created in report builder',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN]
)

MOBILE_USER_DEMO_MODE = StaticToggle(
    'mobile_user_demo_mode',
    'Ability to make a mobile worker into Demo only mobile worker',
    TAG_SOLUTIONS,
    help_link='https://confluence.dimagi.com/display/internal/Demo+Mobile+Workers',
    namespaces=[NAMESPACE_DOMAIN]
)


EXPORT_ZIPPED_APPS = StaticToggle(
    'export-zipped-apps',
    'Export+Import Zipped Applications',
    TAG_INTERNAL,
    [NAMESPACE_USER]
)


SEND_UCR_REBUILD_INFO = StaticToggle(
    'send_ucr_rebuild_info',
    'Notify when UCR rebuilds finish or error.',
    TAG_SOLUTIONS,
    [NAMESPACE_USER]
)

EMG_AND_REC_SMS_HANDLERS = StaticToggle(
    'emg_and_rec_sms_handlers',
    'ILS: Enable emergency and receipt sms handlers used in ILSGateway',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

ALLOW_USER_DEFINED_EXPORT_COLUMNS = StaticToggle(
    'allow_user_defined_export_columns',
    'UPDATE: HQ will not automatically determine the case properties available for an export',
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN],
)


CUSTOM_CALENDAR_FIXTURE = StaticToggle(
    'custom_calendar_fixture',
    'Enikshay: Send a calendar fixture down to all users (R&D)',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

DISABLE_COLUMN_LIMIT_IN_UCR = StaticToggle(
    'disable_column_limit_in_ucr',
    'Disable column limit in UCR',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

CLOUDCARE_LATEST_BUILD = StaticToggle(
    'use_latest_build_cloudcare',
    'Uses latest build for Web Apps instead of latest published',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

USER_TESTING_SIMPLIFY = StaticToggle(
    'user_testing_simplify',
    'Simplify the UI for user testing experiments',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN]
)

# when enabled this should prevent any changes to a domains data
DATA_MIGRATION = StaticToggle(
    'data_migration',
    'Disable submissions and restores during a data migration',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN]
)

EMWF_WORKER_ACTIVITY_REPORT = StaticToggle(
    'emwf_worker_activity_report',
    'Make the Worker Activity Report use the Groups or Users or Locations (LocationRestrictedEMWF) filter',
    TAG_SOLUTIONS,
    namespaces=[NAMESPACE_DOMAIN],
    description=(
        "This flag allows you filter the users to display in the same way as the "
        "other reports - by individual user, group, or location.  Note that this "
        "will also force the report to always display by user."
    ),
)

ENIKSHAY = StaticToggle(
    'enikshay',
    "Enikshay: Enable custom enikshay functionality: additional user and location validation",
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    always_enabled={'enikshay'},
    relevant_environments={'enikshay'},
)

DATA_DICTIONARY = StaticToggle(
    'data_dictionary',
    'Project level data dictionary of cases',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    description='Available in the Data section, shows the names of all properties of each case type.',
)

LINKED_APPS = StaticToggle(
    'linked_apps',
    'Allows master and linked apps',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/ccinternal/Linked+Applications',
)

LOCATION_USERS = StaticToggle(
    'location_users',
    'Enikshay: Autogenerate users for each location',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    description=(
        "This flag adds an option to the location types page (under 'advanced "
        "mode') to create users for all locations of a specified type."
    ),
)

SORT_CALCULATION_IN_CASE_LIST = StaticToggle(
    'sort_calculation_in_case_list',
    'Configure a custom xpath calculation for Sort Property in Case Lists',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN]
)

ANONYMOUS_WEB_APPS_USAGE = StaticToggle(
    'anonymous_web_apps_usage',
    'Allow anonymous users to access Web Apps applications',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN],
    always_disabled={'icds-cas'},
    description='Users are automatically logged into Web Apps as a designated mobile worker.'
)

INCLUDE_METADATA_IN_UCR_EXCEL_EXPORTS = StaticToggle(
    'include_metadata_in_ucr_excel_exports',
    'Include metadata in UCR excel exports',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN]
)

UATBC_ADHERENCE_TASK = StaticToggle(
    'uatbc_adherence_calculations',
    'Enikshay: This runs backend adherence calculations for enikshay domains',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

VIEW_APP_CHANGES = StaticToggle(
    'app-changes-with-improved-diff',
    'Improved app changes view',
    TAG_PRODUCT,
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
)

COUCH_SQL_MIGRATION_BLACKLIST = StaticToggle(
    'couch_sql_migration_blacklist',
    "Domains to exclude from migrating to SQL backend. Includes the following "
    "by default: 'ews-ghana', 'ils-gateway', 'ils-gateway-train'",
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
    always_enabled={
        'ews-ghana', 'ils-gateway', 'ils-gateway-train'
    }
)

PAGINATED_EXPORTS = StaticToggle(
    'paginated_exports',
    'Allows for pagination of exports for very large exports',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN]
)

LOGIN_AS_ALWAYS_OFF = StaticToggle(
    'always_turn_login_as_off',
    'Always turn login as off',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

SHOW_DEV_TOGGLE_INFO = StaticToggle(
    'highlight_feature_flags',
    'Highlight / Mark Feature Flags in the UI',
    TAG_INTERNAL,
    [NAMESPACE_USER]
)

DASHBOARD_GRAPHS = StaticToggle(
    'dashboard_graphs',
    'Show submission graph on dashboard',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

PUBLISH_CUSTOM_REPORTS = StaticToggle(
    'publish_custom_reports',
    "Publish custom reports (No needed Authorization)",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

DISPLAY_CONDITION_ON_TABS = StaticToggle(
    'display_condition_on_nodeset',
    'Show Display Condition on Case Detail Tabs',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN]
)

PHONE_HEARTBEAT = StaticToggle(
    'phone_apk_heartbeat',
    "Ability to configure a mobile feature to prompt "
    "users to update to latest CommCare app and apk",
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN]
)

SKIP_REMOVE_INDICES = StaticToggle(
    'skip_remove_indices',
    'Make _remove_indices_from_deleted_cases_task into a no-op.',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN]
)

PREVENT_MOBILE_UCR_SYNC = StaticToggle(
    'prevent_mobile_ucr_sync',
    'ICDS: Used for ICDS emergencies when UCR sync is killing the DB',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    description='Prevents mobile UCRs from being generated or included in the sync payload',
)

ENABLE_ALL_ADD_ONS = StaticToggle(
    'enable_all_add_ons',
    'Enable all app manager add-ons',
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN]
)

FILTERED_BULK_USER_DOWNLOAD = StaticToggle(
    'filtered_bulk_user_download',
    "Ability to filter mobile workers based on Role and username "
    "when doing bulk download",
    TAG_SOLUTIONS,
    [NAMESPACE_DOMAIN]
)

ICDS_LIVEQUERY = PredictablyRandomToggle(
    'icds_livequery',
    'ICDS: Enable livequery case sync for a random subset of ICDS users',
    TAG_CUSTOM,
    [NAMESPACE_USER],
    randomness=0.0,
)

REMOTE_REQUEST_QUESTION_TYPE = StaticToggle(
    'remote_request_quetion_type',
    'Enikshay: Enable remote request question type in the form builder',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

TWO_FACTOR_SUPERUSER_ROLLOUT = StaticToggle(
    'two_factor_superuser_rollout',
    'Users in this list will be forced to have Two-Factor Auth enabled',
    TAG_INTERNAL,
    [NAMESPACE_USER]
)
