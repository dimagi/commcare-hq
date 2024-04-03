import hashlib
import inspect
import math
from functools import wraps
from importlib import import_module
from typing import List

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from attr import attrib, attrs
from couchdbkit import ResourceNotFound
from memoized import memoized

from corehq import privileges
from corehq.extensions import ResultFormat, extension_point
from corehq.util.quickcache import quickcache

from .models import Toggle
from .shortcuts import set_toggle, toggle_enabled


@attrs(frozen=True)
class Tag:
    name = attrib(type=str)
    css_class = attrib(type=str)
    description = attrib(type=str)

    @property
    def index(self):
        return ALL_TAGS.index(self)


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
TAG_RELEASE = Tag(
    name='Release',
    css_class='release',
    description='This is a feature that is in the process of being released.',
)
TAG_SAAS_CONDITIONAL = Tag(
    name='SaaS - Conditional Use',
    css_class='primary',
    description="When enabled, “SaaS - Conditional Use” feature flags will be fully supported by the SaaS team. "
                "Please confirm with the SaaS Product team before enabling “SaaS - Conditional Use” flags for an external "  # noqa: E501
                "customer."
)
TAG_SOLUTIONS = Tag(
    name='Solutions',
    css_class='info',
    description="These features are only available for our services projects. This may affect support and "
                "pricing when the project is transitioned to a subscription."
)
TAG_SOLUTIONS_OPEN = Tag(
    name='Solutions - Open Use',
    css_class='info',
    description="These features are only available for our services projects. This may affect support and "
                "pricing when the project is transitioned to a subscription. Open Use Solutions Feature Flags can be "  # noqa: E501
                "enabled by GS."
)
TAG_SOLUTIONS_CONDITIONAL = Tag(
    name='Solutions - Conditional Use',
    css_class='info',
    description="These features are only available for our services projects. This may affect support and "
                "pricing when the project is transitioned to a subscription. Conditional Use Solutions Feature Flags can be "  # noqa: E501
                "complicated and should be enabled by GS only after ensuring your partners have the proper training materials."  # noqa: E501
)
TAG_SOLUTIONS_LIMITED = Tag(
    name='Solutions - Limited Use',
    css_class='info',
    description=mark_safe(  # nosec: no user input
        'These features are only available for our services projects. This '
        'may affect support and pricing when the project is transitioned to a '
        'subscription. Limited Use Solutions Feature Flags cannot be enabled '
        'by GS before submitting a <a href="https://docs.google.com/forms/d/e/'
        '1FAIpQLSfsX0K05nqflGdboeRgaa40HMfFb2DjGUbP4cKJL76ieS_TAA/viewform">'
        'SolTech Feature Flag Request</a>.'
    )
)
TAG_INTERNAL = Tag(
    name='Internal Engineering Tools',
    css_class='default',
    description="These are tools for our engineering team to use to manage the product",
)
# Order roughly corresponds to how much we want you to use it
ALL_TAG_GROUPS = [TAG_SOLUTIONS, TAG_PRODUCT, TAG_CUSTOM, TAG_INTERNAL, TAG_RELEASE, TAG_DEPRECATED]
ALL_TAGS = [
    TAG_SOLUTIONS_OPEN,
    TAG_SOLUTIONS_CONDITIONAL,
    TAG_SOLUTIONS_LIMITED,
    TAG_SAAS_CONDITIONAL,
] + ALL_TAG_GROUPS


class StaticToggle(object):

    def __init__(
        self,
        slug,
        label,
        tag,
        namespaces=None,
        help_link=None,
        description=None,
        save_fn=None,
        enabled_for_new_domains_after=None,
        enabled_for_new_users_after=None,
        relevant_environments=None,
        notification_emails=None,
        parent_toggles=None,
    ):
        self.slug = slug
        self.label = label
        self.tag = tag
        self.help_link = help_link
        self.description = description
        # Optionally provide a callable to be called whenever the toggle is
        # updated.  This is only applicable to domain toggles.  It must accept
        # two parameters, `domain_name` and `toggle_is_enabled`
        self.save_fn = save_fn
        # Toggles can be declared in localsettings statically
        #   to avoid cache lookups
        self.always_enabled = set(
            settings.STATIC_TOGGLE_STATES.get(self.slug, {}).get('always_enabled', []))
        self.always_disabled = set(
            settings.STATIC_TOGGLE_STATES.get(self.slug, {}).get('always_disabled', []))
        self.enabled_for_new_domains_after = enabled_for_new_domains_after
        self.enabled_for_new_users_after = enabled_for_new_users_after
        # pass in a set of environments where this toggle applies
        self.relevant_environments = relevant_environments

        parent_toggles = parent_toggles or []
        for dependency in parent_toggles:
            parent_toggles.extend(dependency.parent_toggles)

        self.parent_toggles = parent_toggles

        if namespaces:
            self.namespaces = [None if n == NAMESPACE_USER else n for n in namespaces]
        else:
            self.namespaces = [None]
        self.notification_emails = notification_emails

        for dependency in self.parent_toggles:
            if not set(self.namespaces) & set(dependency.namespaces):
                raise Exception(
                    "Namespaces of dependent toggles must overlap with dependency:"
                    f" {self.slug}, {dependency.slug}")

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
        ) or (
            NAMESPACE_EMAIL_DOMAIN in self.namespaces
            and hasattr(request, 'user')
            and self.enabled(
                request.user.email or request.user.username,
                namespace=NAMESPACE_EMAIL_DOMAIN
            )
        )

    def set(self, item, enabled, namespace=None):
        if namespace == NAMESPACE_USER:
            namespace = None  # because:
            #     __init__() ... self.namespaces = [None if n == NAMESPACE_USER else n for n in namespaces]

        if namespace not in self.namespaces:
            return False

        return set_toggle(self.slug, item, enabled, namespace)

    def required_decorator(self):
        """
        Returns a view function decorator that checks to see if the domain
        or user in the request has the appropriate toggle enabled.
        """

        def decorator(view_func):
            @wraps(view_func)
            def wrapped_view(request, *args, **kwargs):
                if self.enabled_for_request(request):
                    return view_func(request, *args, **kwargs)
                if request.user.is_superuser:
                    from corehq.apps.toggle_ui.views import ToggleEditView
                    toggle_url = reverse(ToggleEditView.urlname, args=[self.slug])
                    messages.warning(
                        request,
                        format_html(
                            'This <a href="{}">feature flag</a> should be enabled '
                            'to access this URL',
                            toggle_url
                        ),
                        fail_silently=True,  # workaround for tests: https://code.djangoproject.com/ticket/17971
                    )
                raise Http404()

            return wrapped_view

        return decorator

    def get_enabled_domains(self):
        try:
            toggle = Toggle.get(self.slug)
        except ResourceNotFound:
            return []

        enabled_users = toggle.enabled_users
        domains = {user.split('domain:')[1] for user in enabled_users if 'domain:' in user}
        domains |= self.always_enabled
        domains -= self.always_disabled
        return list(domains)

    def get_enabled_users(self):
        try:
            toggle = Toggle.get(self.slug)
        except ResourceNotFound:
            return []

        return [user for user in toggle.enabled_users if not user.startswith("domain:")]


def was_domain_created_after(domain, checkpoint):
    """
    Return true if domain was created after checkpoint

    :param domain: Domain name (string).
    :param checkpoint: datetime object.
    """
    from corehq.apps.domain.models import Domain
    domain_obj = Domain.get_by_name(domain)
    return (
        domain_obj is not None
        and domain_obj.date_created is not None
        and domain_obj.date_created > checkpoint
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
        user is not None
        and user.created_on is not None
        and user.created_on > checkpoint
    )


def deterministic_random(input_string):
    """
    Returns a deterministically random number between 0 and 1 based on the
    value of the string. The same input should always produce the same output.
    """
    if isinstance(input_string, str):
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
        relevant_environments=None,
        notification_emails=None,
        parent_toggles=None
    ):
        super(PredictablyRandomToggle, self).__init__(slug, label, tag, list(namespaces),
                                                      help_link=help_link, description=description,
                                                      relevant_environments=relevant_environments,
                                                      notification_emails=notification_emails,
                                                      parent_toggles=parent_toggles)
        _ensure_valid_namespaces(namespaces)
        _ensure_valid_randomness(randomness)
        self.randomness = randomness

    @property
    def randomness_percent(self):
        return "{:.0f}".format(self.randomness * 100)

    def _get_identifier(self, item):
        return '{}:{}:{}'.format(self.namespaces, self.slug, item)

    def enabled(self, item, namespace=Ellipsis):
        if self.relevant_environments and not (
            settings.SERVER_ENVIRONMENT in self.relevant_environments
            or settings.DEBUG
        ):
            # Don't even bother looking it up in the cache
            return False

        if namespace == NAMESPACE_USER:
            namespace = None  # because:
            # StaticToggle.__init__(): self.namespaces = [None if n == NAMESPACE_USER else n for n in namespaces]

        all_namespaces = {None if n == NAMESPACE_USER else n for n in ALL_RANDOM_NAMESPACES}
        if namespace is Ellipsis and set(self.namespaces) != all_namespaces:
            raise ValueError(
                'PredictablyRandomToggle.enabled() cannot be determined for toggle "{slug}" because it is not '
                'available for all namespaces and the namespace of "{item}" is not given.'.format(
                    slug=self.slug,
                    item=item,
                )
            )

        if settings.DISABLE_RANDOM_TOGGLES:
            return False
        elif item in self.always_disabled:
            return False
        elif namespace is not Ellipsis and namespace not in self.namespaces:
            return False
        return (
            (item and deterministic_random(self._get_identifier(item)) < self.randomness)
            or super(PredictablyRandomToggle, self).enabled(item, namespace)
        )


class DynamicallyPredictablyRandomToggle(PredictablyRandomToggle):
    """
    A PredictablyRandomToggle whose randomness can be configured via the database/UI.
    """
    RANDOMNESS_KEY = 'hq_dynamic_randomness'

    def __init__(
        self,
        slug,
        label,
        tag,
        namespaces,
        default_randomness=0.0,
        help_link=None,
        description=None,
        relevant_environments=None,
        notification_emails=None,
        parent_toggles=None
    ):
        super(PredictablyRandomToggle, self).__init__(slug, label, tag, list(namespaces),
                                                      help_link=help_link, description=description,
                                                      relevant_environments=relevant_environments,
                                                      notification_emails=notification_emails,
                                                      parent_toggles=parent_toggles)
        _ensure_valid_namespaces(namespaces)
        _ensure_valid_randomness(default_randomness)
        self.default_randomness = default_randomness

    @property
    @quickcache(vary_on=['self.slug'])
    def randomness(self):
        # a bit hacky: leverage couch's dynamic properties to just tack this onto the couch toggle doc
        try:
            toggle = Toggle.get(self.slug)
        except ResourceNotFound:
            return self.default_randomness
        dynamic_randomness = getattr(toggle, self.RANDOMNESS_KEY, self.default_randomness)
        try:
            dynamic_randomness = float(dynamic_randomness)
            return dynamic_randomness
        except ValueError:
            return self.default_randomness


class FeatureRelease(DynamicallyPredictablyRandomToggle):
    """This class is designed to allow release of features in a controlled manner.
    The primary purpose is to decouple code deploys from feature releases.

    In addition the normal arguments, feature release toggles must also provide
    an 'owner' to indicate the member of the team responsible for releasing this feature.
    This will be displayed on the UI when editing the toggle.
    """

    def __init__(
        self,
        slug,
        label,
        tag,
        namespaces,
        owner,
        default_randomness=0.0,
        help_link=None,
        description=None,
        relevant_environments=None,
        notification_emails=None,
        parent_toggles=None
    ):
        super().__init__(
            slug, label, tag, namespaces,
            default_randomness=default_randomness,
            help_link=help_link,
            description=description,
            relevant_environments=relevant_environments,
            notification_emails=notification_emails,
            parent_toggles=parent_toggles
        )
        self.owner = owner


# if no namespaces are specified the user namespace is assumed
NAMESPACE_USER = 'user'
NAMESPACE_DOMAIN = 'domain'
NAMESPACE_EMAIL_DOMAIN = 'email_domain'
NAMESPACE_OTHER = 'other'
ALL_NAMESPACES = [NAMESPACE_USER, NAMESPACE_DOMAIN, NAMESPACE_EMAIL_DOMAIN]
ALL_RANDOM_NAMESPACES = [NAMESPACE_USER, NAMESPACE_DOMAIN]


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


@extension_point(result_format=ResultFormat.FLATTEN)
def custom_toggle_modules() -> List[str]:
    """Extension point to add toggles from custom code

    Parameters:
        None

    Returns:
        List of python module strings for custom toggle modules.
    """


def all_toggles():
    """
    Loads all toggles
    """
    return list(all_toggles_by_name().values())


def all_toggle_slugs():
    """
    Provides all toggles by their slug as a list
    """
    return [toggle.slug for toggle in all_toggles()]


@memoized
def all_toggles_by_name():
    # trick for listing the attributes of the current module.
    # http://stackoverflow.com/a/990450/8207
    core_toggles = all_toggles_by_name_in_scope(globals())
    for module_name in custom_toggle_modules():
        module = import_module(module_name)
        core_toggles.update(all_toggles_by_name_in_scope(module.__dict__))
    return core_toggles


def all_toggles_by_name_in_scope(scope_dict, toggle_class=StaticToggle):
    result = {}
    for toggle_name, toggle in scope_dict.items():
        if not toggle_name.startswith('__'):
            if toggle_class == FrozenPrivilegeToggle:
                # Include only FrozenPrivilegeToggle types
                include = isinstance(toggle, FrozenPrivilegeToggle)
            else:
                # Exclude FrozenPrivilegeToggle but include other subclasses such as FeatureRelease
                include = isinstance(toggle, toggle_class) and not isinstance(toggle, FrozenPrivilegeToggle)
            if include:
                result[toggle_name] = toggle
    return result


def toggles_dict(username=None, domain=None):
    """
    Loads all toggles into a dictionary for use in JS

    (only enabled toggles are included)
    """
    by_name = all_toggles_by_name()
    enabled = set()
    if username:
        enabled |= toggles_enabled_for_user(username)
    if domain:
        enabled |= toggles_enabled_for_domain(domain)
    return {by_name[name].slug: True for name in enabled if name in by_name}


def toggle_values_by_name(username, domain):
    """
    Loads all toggles into a dictionary for use in JS
    """
    all_enabled = toggles_enabled_for_user(username) | toggles_enabled_for_domain(domain)

    return {
        toggle_name: toggle_name in all_enabled
        for toggle_name in all_toggles_by_name().keys()
    }


@quickcache(["domain"], timeout=24 * 60 * 60, skip_arg=lambda _: settings.UNIT_TESTING)
def toggles_enabled_for_domain(domain):
    """Return set of toggle names that are enabled for the given domain"""
    return {
        toggle_name
        for toggle_name, toggle in all_toggles_by_name().items()
        if toggle.enabled(domain, NAMESPACE_DOMAIN)
    }


@quickcache(["username"], timeout=24 * 60 * 60, skip_arg=lambda _: settings.UNIT_TESTING)
def toggles_enabled_for_user(username):
    """Return set of toggle names that are enabled for the given user"""
    return {
        toggle_name
        for toggle_name, toggle in all_toggles_by_name().items()
        if toggle.enabled(username, NAMESPACE_USER)
    }


@quickcache(["email"], timeout=24 * 60 * 60, skip_arg=lambda _: settings.UNIT_TESTING)
def toggles_enabled_for_email_domain(email):
    """Return set of toggle names that are enabled for the given email"""
    return {
        toggle_name
        for toggle_name, toggle in all_toggles_by_name().items()
        if toggle.enabled(email, NAMESPACE_EMAIL_DOMAIN)
    }


def toggles_enabled_for_request(request):
    """Return set of toggle names that are enabled for a particular request"""
    toggles = set()

    if hasattr(request, 'domain'):
        toggles = toggles | toggles_enabled_for_domain(request.domain)

    if hasattr(request, 'user'):
        toggles = toggles | toggles_enabled_for_user(request.user.username)
        toggles = toggles | toggles_enabled_for_email_domain(getattr(request.user, 'email', request.user.username))

    return toggles


def _ensure_valid_namespaces(namespaces):
    if not namespaces:
        raise Exception('namespaces must be defined!')


def _ensure_valid_randomness(randomness):
    if not 0 <= randomness <= 1:
        raise Exception('randomness must be between 0 and 1!')


APP_BUILDER_CUSTOM_PARENT_REF = StaticToggle(
    'custom-parent-ref',
    'ICDS: Custom case parent reference',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

LAZY_LOAD_MULTIMEDIA = StaticToggle(
    'optional-media',
    'ICDS: Lazy load multimedia files in Updates',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

APP_BUILDER_ADVANCED = StaticToggle(
    'advanced-app-builder',
    'Advanced Module in App-Builder',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN],
    description="Advanced Modules allow you to autoload and manage multiple case types, "
                "but may behave in unexpected ways.",
    help_link='https://confluence.dimagi.com/display/saas/Advanced+Modules',
)

APP_BUILDER_SHADOW_MODULES = StaticToggle(
    'shadow-app-builder',
    'Shadow Modules',
    TAG_SOLUTIONS_CONDITIONAL,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/Shadow+Modules+and+Forms',
)

V1_SHADOW_MODULES = StaticToggle(
    'v1-shadows',
    'Allow creation and management of deprecated Shadow Module behaviour',
    TAG_SOLUTIONS_CONDITIONAL,
    [NAMESPACE_DOMAIN],
    help_link='https://github.com/dimagi/commcare-hq/blob/master/docs/apps/advanced_app_features.rst#shadow-modules',  # noqa
)

CASE_LIST_CUSTOM_XML = StaticToggle(
    'case_list_custom_xml',
    'Allow custom XML to define case lists (ex. for case tiles)',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/pages/viewpage.action?'
              'spaceKey=saas&title=Allow+Configuration+of+Case+List+Tiles',
)

CASE_LIST_CUSTOM_VARIABLES = StaticToggle(
    'case_list_custom_variables',
    'Show editor for entering custom variables',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN],
    description='Defines custom variables that can be used in case list or detail calculations',
)

CASE_LIST_TILE = StaticToggle(
    'case_list_tile',
    'REC/USH: Case tile templates',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/pages/viewpage.action?'
              'spaceKey=saas&title=Allow+Configuration+of+Case+List+Tiles',
)

CASE_LIST_TILE_CUSTOM = StaticToggle(
    'case_list_tile_custom',
    'USH: Configure custom case tile for case list and case detail',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/pages/viewpage.action?'
              'spaceKey=saas&title=Allow+Configuration+of+Case+List+Tiles',
    parent_toggles=[CASE_LIST_TILE],
)

CASE_LIST_MAP = StaticToggle(
    'case_list_map',
    'USH: Allow use of a map in the case list in Web Apps',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/pages/viewpage.action?'
              'spaceKey=saas&title=Allow+Configuration+of+Case+List+Tiles',
)

CASE_LIST_LAZY = StaticToggle(
    'case_list_lazy',
    'USH: Add option to lazy load case list',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/pages/viewpage.action?'
              'spaceKey=saas&title=Allow+Configuration+of+Case+List+Lazy',
)

SHOW_PERSIST_CASE_CONTEXT_SETTING = StaticToggle(
    'show_persist_case_context_setting',
    'Allow toggling the persistent case context tile',
    TAG_SOLUTIONS_CONDITIONAL,
    [NAMESPACE_DOMAIN],
)

FORM_LINK_ADVANCED_MODE = StaticToggle(
    'form_link_advanced_mode',
    'USH: Form linking advanced mode',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    description=(
        "Switches manual datum configuration for form linking to a UI where app "
        "builders must specify the datum IDs to provide. Allows for linking to "
        "more targets, but is way harder to use."
    ),
)

CASE_LIST_LOOKUP = StaticToggle(
    'case_list_lookup',
    'Allow external android callouts to search the case list',
    TAG_SOLUTIONS_CONDITIONAL,
    [NAMESPACE_DOMAIN]
)

SSO_REMOTE_USER_MANAGEMENT = StaticToggle(
    'sso_remote_user_management',
    "Shows remote user management fields in SSO Identity Provider Form",
    TAG_PRODUCT,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

BIOMETRIC_INTEGRATION = StaticToggle(
    'biometric_integration',
    "Enables biometric integration (simprints) features.",
    TAG_PRODUCT,
    [NAMESPACE_DOMAIN]
)

ADD_USERS_FROM_LOCATION = StaticToggle(
    'add_users_from_location',
    "Allow users to add new mobile workers from the locations page",
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN]
)

CASE_DETAIL_PRINT = StaticToggle(
    'case_detail_print',
    'MLabour: Allowing printing of the case detail, based on an HTML template',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

COPY_FORM_TO_APP = StaticToggle(
    'copy_form_to_app',
    'Allow copying a form from one app to another',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
)

DETAIL_LIST_TAB_NODESETS = StaticToggle(
    'detail-list-tab-nodesets',
    'Associate a nodeset with a case detail tab',
    TAG_SOLUTIONS_CONDITIONAL,
    help_link='https://confluence.dimagi.com/display/saas/Case+Detail+Nodesets',
    namespaces=[NAMESPACE_DOMAIN]
)

DHIS2_INTEGRATION = StaticToggle(
    'dhis2_integration',
    'DHIS2 Integration',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN]
)

GRAPH_CREATION = StaticToggle(
    'graph-creation',
    'Case list/detail graph creation',
    TAG_SOLUTIONS_CONDITIONAL,
    help_link='https://confluence.dimagi.com/display/GTDArchive/Graphing+in+HQ',
    namespaces=[NAMESPACE_DOMAIN]
)

IS_CONTRACTOR = StaticToggle(
    'is_contractor',
    'Is contractor',
    TAG_INTERNAL,
    description="Used to give non super-users access to select super-user features"
)

MM_CASE_PROPERTIES = StaticToggle(
    'mm_case_properties',
    'Multimedia Case Properties',
    TAG_DEPRECATED,
    help_link='https://confluence.dimagi.com/display/saas/Multimedia+Case+Properties+Feature+Flag',
    namespaces=[NAMESPACE_DOMAIN],
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
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
    description=(
        "A feature which will allow your domain to create User Configurable Reports."
    ),
    help_link='https://confluence.dimagi.com/display/GTDArchive/User+Configurable+Reporting',
)

UCR_UPDATED_NAMING = StaticToggle(
    'ucr_updated_naming',
    'Show updated naming of UCRS',
    TAG_SAAS_CONDITIONAL,
    [NAMESPACE_DOMAIN],
    description=(
        "Displays updated UCR naming if the feature flag is enabled."
        "This is a temporary flag which would be removed when the updated naming is agreed upon by all divisons."
    )
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

UCR_SUM_WHEN_TEMPLATES = StaticToggle(
    'ucr_sum_when_templates',
    'Allow sum when template columns in dynamic UCRs',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    description=(
        "Enables use of SumWhenTemplateColumn with custom expressions in dynamic UCRS."
    ),
    help_link='https://commcare-hq.readthedocs.io/ucr.html#sumwhencolumn-and-sumwhentemplatecolumn',
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
                "We are actively trying to remove projects from this list. This functionality is now possible by using the "  # noqa: E501
                "Advanced Settings on the Organization Levels page and setting the Level to Expand From option.",
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
    'Enable extension syncing',
    TAG_SOLUTIONS_CONDITIONAL,
    help_link='https://confluence.dimagi.com/display/saas/Extension+Cases',
    namespaces=[NAMESPACE_DOMAIN],
)

USH_DONT_CLOSE_PATIENT_EXTENSIONS = StaticToggle(
    'ush_dont_close_patient_extensions',
    'USH: Suppress closing extensions on closing hosts for host/extension pairs of patient/contact case-types',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    Suppress the normal behaviour of 'closing host cases closes its extension cases'.
    Enabling this results in 'closing patient type cases will not close its contact type
    extension cases'. Designed for specific USH domain use-case
    """
)

DISABLE_WEB_APPS = StaticToggle(
    'disable_web_apps',
    'Disable access to Web Apps UI',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/Disable+access+to+Web+Apps+UI',
)

WEB_APPS_DOMAIN_BANNER = StaticToggle(
    'web_apps_domain_banner',
    'USH: Show current domain in web apps Log In As banner',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/USH%3A+Show+current+domain+in+web+apps+Login+As+banner',
)

WEB_APPS_UPLOAD_QUESTIONS = FeatureRelease(
    'web_apps_upload_questions',
    'USH: Support image, audio, and video questions in Web Apps',
    TAG_RELEASE,
    namespaces=[NAMESPACE_DOMAIN],
    owner='Jenny Schweers',
)

WEB_APPS_ANCHORED_SUBMIT = StaticToggle(
    'web_apps_anchored_submit',
    'USH: Keep submit button anchored at the bottom of screen for forms in Web Apps',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

SYNC_SEARCH_CASE_CLAIM = StaticToggle(
    'search_claim',
    'Enable synchronous mobile searching and case claiming',
    TAG_SOLUTIONS_CONDITIONAL,
    help_link='https://confluence.dimagi.com/display/saas/Case+Search+and+Claim',
    namespaces=[NAMESPACE_DOMAIN]
)

USH_CASE_LIST_MULTI_SELECT = StaticToggle(
    'ush_case_list_multi_select',
    'USH: Allow selecting multiple cases from the case list',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/USH%3A+Allow+selecting+multiple+cases+from+the+case+list',  # noqa: E501
    description="""
    Allows user to select multiple cases and load them all into the form.
    """
)

USH_CASE_CLAIM_UPDATES = StaticToggle(
    'case_claim_autolaunch',
    "USH Specific toggle to support several different case search/claim workflows in web apps",
    TAG_CUSTOM,
    help_link='https://confluence.dimagi.com/display/USH/Case+Search+Configuration',
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    USH Specific toggle to support several different case search/claim workflows in web apps:
    "search first", "see more", and "skip to default case search results", Geocoder
    and other options in Webapps Case Search.
    """,
    parent_toggles=[SYNC_SEARCH_CASE_CLAIM]
)

GEOCODER_MY_LOCATION_BUTTON = StaticToggle(
    "geocoder_my_location_button",
    "USH: Add button to geocoder to populate search with the user's current location",
    TAG_RELEASE,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    When enabled this will add a small button to the geocoder widget that, when pressed, and if
    the user grants permission, will perform a reverse geocoding query based on the user's reported location.
    The result will be used to populate the search field of the geocoder widget.

    This is intended as a temporary toggle and will likely get rolled into the "USH_CASE_CLAIM_UPDATES" toggle.
    """,
    parent_toggles=[USH_CASE_CLAIM_UPDATES],
)

GEOCODER_AUTOLOAD_USER_LOCATION = StaticToggle(
    "geocoder_autoload_user_location",
    "USH: Auto-load the geocoder widget with the user's current location",
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    When enabled, and if the user grants permissions, the geocoder widget will automatically do a reverse
    geocoding query using the user's reported location The result will be used to populate the search field
    of the geocoder widget.
    """,
    parent_toggles=[USH_CASE_CLAIM_UPDATES],
)

GEOCODER_USER_PROXIMITY = StaticToggle(
    "geocoder_user_proximity",
    "USH: Adjust geocoder result to be more relevant to user and project.",
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    This has two effects on getting geocoder search results:
    1. Based on the bounding box of the project default location all result falling outside of it
       will be filtered out when used in the case search.
    2. Proximity to the users location will be taken into account for the results order.
    """,
    parent_toggles=[USH_CASE_CLAIM_UPDATES],
)

USH_SEARCH_FILTER = StaticToggle(
    'case_search_filter',
    "USH Specific toggle to use Search Filter in case search options.",
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    parent_toggles=[SYNC_SEARCH_CASE_CLAIM]
)

USH_INLINE_SEARCH = StaticToggle(
    'inline_case_search',
    "USH Specific toggle to making case search user input available to other parts of the app.",
    TAG_CUSTOM,
    help_link='https://docs.google.com/document/d/1Mmx1FrYZrcEmWidqSkNjC_gWSJ6xzRFKoP3Rn_xSaj4/edit#',
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    Temporary toggle to manage the release of the 'inline search' / 'case search input' feature.
    """,
    parent_toggles=[USH_CASE_CLAIM_UPDATES]
)

USH_EMPTY_CASE_LIST_TEXT = StaticToggle(
    'empty_case_list_text',
    "USH: Allow customizing the text displayed when case list contains no cases in web apps",
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN]
)

SPLIT_SCREEN_CASE_SEARCH = StaticToggle(
    'split_screen_case_search',
    "Split screen case search: In case search, show the search filters in a sidebar on the left and the results"
    " on the right.",
    TAG_CUSTOM,
    help_link='https://confluence.dimagi.com/display/USH/Split+Screen+Case+Search',
    namespaces=[NAMESPACE_DOMAIN],
    parent_toggles=[SYNC_SEARCH_CASE_CLAIM]
)

DYNAMICALLY_UPDATE_SEARCH_RESULTS = StaticToggle(
    'dynamically_update_search_results',
    "In case search with split screen case search enabled, search results update when a search field is updated"
    " without requiring the user to manually press a button to search.",
    TAG_CUSTOM,
    help_link='https://confluence.dimagi.com/display/USH/Split+Screen+Case+Search',
    namespaces=[NAMESPACE_DOMAIN],
    parent_toggles=[SPLIT_SCREEN_CASE_SEARCH]
)

USH_USERCASES_FOR_WEB_USERS = StaticToggle(
    'usercases_for_web_users',
    "USH: Enable the creation of usercases for web users.",
    TAG_CUSTOM,
    help_link='https://confluence.dimagi.com/display/saas/USH%3A+Enable+Web+User+Usercase+Creation',
    namespaces=[NAMESPACE_DOMAIN],
)

WEBAPPS_STICKY_SEARCH = StaticToggle(
    "webapps_sticky_search",
    "USH: Sticky search: In web apps, save user's most recent inputs on case search & claim screen.",
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/COVID%3A+Web+Apps+Sticky+Search',
)

HIDE_SYNC_BUTTON = StaticToggle(
    "hide_sync_button",
    "USH: Hide Sync Button in Web Apps",
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

MULTI_VIEW_API_KEYS = StaticToggle(
    'multi_view_api_keys',
    "Multi-View API Keys",
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description="Allows users to view and copy API keys after creation",
)


def _ensure_search_index_is_enabled(domain, enabled):
    from corehq.apps.case_search.tasks import reindex_case_search_for_domain
    from corehq.apps.es import CaseSearchES
    from corehq.pillows.case_search import domain_needs_search_index
    from corehq.apps.case_search.models import DomainsNotInCaseSearchIndex

    if enabled and DomainsNotInCaseSearchIndex.objects.filter(domain=domain).exists():
        DomainsNotInCaseSearchIndex.objects.filter(domain=domain).delete()
        domain_needs_search_index.clear(domain)

    has_case_search_cases = CaseSearchES().domain(domain).count() > 0
    if enabled and not has_case_search_cases:
        reindex_case_search_for_domain.delay(domain)


EXPLORE_CASE_DATA = StaticToggle(
    'explore_case_data',
    'Show the Explore Case Data report (in dev)',
    TAG_PRODUCT,
    namespaces=[NAMESPACE_DOMAIN, NAMESPACE_USER],
    description='Show the Explore Case Data report (in dev). Please make sure the project '
    'is fully migrated to support the CaseSearch index either by enabling '
    'the Case List Explorer toggle or doing a manual migration.\n\n'
    'Please use the EXPLORE_CASE_DATA_PREVIEW Feature Preview moving forward. '
    'This will be deprecated once the Feature Preview is in full swing.',
)

ECD_MIGRATED_DOMAINS = StaticToggle(
    'ecd_migrated_domains',
    'Explore Case Data for domains that have undergone migration',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
    description='Domains that have undergone migration for Explore Case Data and have a '
    'CaseSearch elasticsearch index created.\n\n'
    'NOTE: enabling this Feature Flag will NOT enable the CaseSearch index.'
)

ECD_PREVIEW_ENTERPRISE_DOMAINS = StaticToggle(
    'ecd_enterprise_domains',
    'Explore Case Data feature preview for Enterprise domains',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
    description='Enterprise Domains that are eligible to view the Explore Case Data '
    'Feature Preview. By default, this feature will only be available for '
    'domains that are Advanced or Pro and have undergone the ECD migration.'
)

CASE_API_V0_6 = StaticToggle(
    'case_api_v0_6',
    'Enable the v0.6 Case API',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    save_fn=_ensure_search_index_is_enabled,
)

ACTION_TIMES_API = StaticToggle(
    'action_times_api',
    'Enable the Action Times API',
    TAG_CUSTOM,
    help_link='https://confluence.dimagi.com/display/GTD/Action+Times+API',
    namespaces=[NAMESPACE_USER],
)

HIPAA_COMPLIANCE_CHECKBOX = StaticToggle(
    'hipaa_compliance_checkbox',
    'Show HIPAA compliance checkbox',
    TAG_INTERNAL,
    [NAMESPACE_USER],
)

CAN_EDIT_EULA = StaticToggle(
    'can_edit_eula',
    "Allow user to set the custom EULA and data sharing project options.",
    TAG_INTERNAL,
    description="Whether this user can set the custom eula and data sharing internal project options. "
    "This should be a small number of DIMAGI ONLY users"
)

# This toggle offers the "multiple_apps_unlimited" mobile flag to non-Dimagi users
MOBILE_PRIVILEGES_FLAG = StaticToggle(
    'mobile_privileges_flag',
    'Offer "Enable Privileges on Mobile" flag.',
    TAG_INTERNAL,
    [NAMESPACE_USER]
)

PRODUCTS_PER_LOCATION = StaticToggle(
    'products_per_location',
    "Products Per Location: Specify products stocked at individual locations.",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    description="This doesn't actually do anything yet."
)

ALLOW_CASE_ATTACHMENTS_VIEW = StaticToggle(
    'allow_case_attachments_view',
    "Explicitly allow user to access case attachments, even if they can't view the case list report.",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

TRANSFER_DOMAIN = StaticToggle(
    'transfer_domain',
    'Transfer domains to different users',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN]
)

SECURE_SESSION_TIMEOUT = StaticToggle(
    'secure_session_timeout',
    "USH: Allow domain to override default length of inactivity timeout",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/Allow+domain+to+override+default+length+of+inactivity+timeout",  # noqa: E501
)

# not referenced in code directly but passed through to vellum
# see toggles_dict

VELLUM_SAVE_TO_CASE = StaticToggle(
    'save_to_case',
    "Adds save to case as a question to the form builder",
    TAG_SAAS_CONDITIONAL,
    [NAMESPACE_DOMAIN],
    description='This flag allows case management inside repeat groups',
    help_link='https://confluence.dimagi.com/display/saas/Save+to+Case+Feature+Flag',
)

VELLUM_PRINTING = StaticToggle(
    'printing',
    "Enables the Print Android App Callout",
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN],
    description='Allows printing from CommCare on the device',
    help_link='https://confluence.dimagi.com/display/saas/Printing+from+a+form+in+CommCare+Android',
)

VELLUM_DATA_IN_SETVALUE = StaticToggle(
    'allow_data_reference_in_setvalue',
    "Allow data references in a setvalue",
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN],
    description="This allows referencing other questions in the form in a setvalue. "
                "This may still cause issues if the other questions have not been calculated yet",
)

VELLUM_ALLOW_BULK_FORM_ACTIONS = StaticToggle(
    'allow_bulk_form_actions',
    "Allow bulk form actions in the Form Builder",
    TAG_PRODUCT,
    [NAMESPACE_DOMAIN],
    description="This shows Bulk Form Actions (mark all questions required, "
                "set default values to matching case properties) in "
                "the Form Builder's main dropdown menu.",
)

CACHE_AND_INDEX = StaticToggle(
    'cache_and_index',
    'REC: Enable the "Cache and Index" format option when choosing sort properties '
    'in the app builder',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/pages/viewpage.action?pageId=41484944',
)

CUSTOM_PROPERTIES = StaticToggle(
    'custom_properties',
    'Allow users to add arbitrary custom properties to their application',
    TAG_SOLUTIONS_LIMITED,
    help_link='https://confluence.dimagi.com/display/GS/CommCare+Android+Developer+Options+--+Internal#'
              'CommCareAndroidDeveloperOptions--Internal-SettingtheValueofaDeveloperOptionfromHQ',
    namespaces=[NAMESPACE_DOMAIN]
)

MOBILE_UCR = StaticToggle(
    'mobile_ucr',
    ('Mobile UCR: Configure viewing user configurable reports on the mobile '
     'through the app builder'),
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    parent_toggles=[USER_CONFIGURABLE_REPORTS]
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
    domain_obj = Domain.get_by_name(domain_name, strict=True)
    if domain_obj and domain_obj.commtrack_enabled != toggle_is_enabled:
        if toggle_is_enabled:
            domain_obj.convert_to_commtrack()
        else:
            domain_obj.commtrack_enabled = False
            domain_obj.save()


COMMTRACK = StaticToggle(
    'commtrack',
    "CommCare Supply",
    TAG_SOLUTIONS_LIMITED,
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
    "Enable ledgers for projects not using Supply.",
    TAG_CUSTOM,
    description=(
        'Turns on the ledger fixture and ledger transaction question types in '
        'the form builder. ONLY WORKS ON SQL DOMAINS!'
    ),
    namespaces=[NAMESPACE_DOMAIN],
)

CUSTOM_INSTANCES = StaticToggle(
    'custom_instances',
    'Inject custom instance declarations',
    TAG_CUSTOM,
    description=(
        'Enables the insertion of custom instances into a case list configuration. '
        'Currently used by SimPrints-integrated projects.'
    ),
    namespaces=[NAMESPACE_DOMAIN],
)

CUSTOM_ASSERTIONS = StaticToggle(
    'custom_assertions',
    'Inject custom assertions into the suite',
    TAG_SOLUTIONS_CONDITIONAL,
    description=(
        'Enables the insertion of custom assertions into the suite file. '
    ),
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/User+defined+assert+blocks",
)

OPENMRS_INTEGRATION = StaticToggle(
    'openmrs_integration',
    'Enable OpenMRS integration',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN],
)

SUPPORT = StaticToggle(
    'support',
    'General toggle for support features',
    TAG_INTERNAL,
    help_link='https://confluence.dimagi.com/display/saas/Support+Flag',
)

LEGACY_CHILD_MODULES = StaticToggle(
    'legacy_child_modules',
    'Legacy, non-nested sub-menus',
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN],
    description=(
        "Sub-menus are now displayed nested under their parent menu. Some "
        "apps built before this change will require that their modules be "
        "reordered to fit this paradigm. This feature flag exists to support "
        "those applications until they're transitioned."
    )
)

NON_PARENT_MENU_SELECTION = StaticToggle(
    'non_parent_menu_selection',
    'Allow selecting of module of any case-type in select-parent workflow',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description="Allow selecting of module of any case-type in select-parent workflow",
    help_link="https://confluence.dimagi.com/display/USH/Selecting+any+case+in+%27select+parent+first%27+workflow"
)

FIXTURE_CASE_SELECTION = StaticToggle(
    'fixture_case',
    'ICDS: Allow a configurable case list that is filtered based on a fixture type and '
    'fixture selection (Due List)',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

SMS_LOG_CHANGES = StaticToggle(
    'sms_log_changes',
    'Message Log Report v2',
    TAG_SOLUTIONS_OPEN,
    [NAMESPACE_USER, NAMESPACE_DOMAIN],
    description=("This flag makes failed messages appear in the Message Log "
                 "Report, and adds Status and Event columns"),
)

EXPORT_DATA_SOURCE_DATA = StaticToggle(
    'export_data_source_data',
    'Add Export Data Source Data page',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_USER, NAMESPACE_DOMAIN],
    description="Add the Export Data Source Data page to the Data tab",
)


ENABLE_INCLUDE_SMS_GATEWAY_CHARGING = StaticToggle(
    'enable_include_sms_gateway_charging',
    'Enable include SMS gateway charging',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

MESSAGE_LOG_METADATA = StaticToggle(
    'message_log_metadata',
    'Include message id in Message Log export.',
    TAG_CUSTOM,
    [NAMESPACE_USER],
)

RICH_TEXT_EMAILS = StaticToggle(
    'rich_text_emails',
    'Enable sending rich text HTML emails in conditional alerts and broadcasts',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

RUN_AUTO_CASE_UPDATES_ON_SAVE = StaticToggle(
    'run_auto_case_updates_on_save',
    'Run Auto Case Update rules on each case save.',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
)

CASE_DEDUPE_UPDATES = StaticToggle(
    'case_dedupe_updates',
    'Allow Case deduplication update actions',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/Surfacing+Case+Duplicates+in+CommCare',
)

LEGACY_SYNC_SUPPORT = StaticToggle(
    'legacy_sync_support',
    "Support mobile sync bugs in older projects (2.9 and below).",
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN]
)

CALL_CENTER_LOCATION_OWNERS = StaticToggle(
    'call_center_location_owners',
    'ICDS: Enable the use of locations as owners of call center cases',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

CUSTOM_APP_BASE_URL = StaticToggle(
    'custom_app_base_url',
    'Allow specifying a custom base URL for an application.',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN],
    description="Main use case is to allow migrating projects to a new cluster."
)

PHONE_NUMBERS_REPORT = StaticToggle(
    'phone_numbers_report',
    "Report related to the phone numbers owned by a project's contacts",
    TAG_SOLUTIONS_CONDITIONAL,
    [NAMESPACE_DOMAIN]
)

INBOUND_SMS_LENIENCY = StaticToggle(
    'inbound_sms_leniency',
    "Inbound SMS leniency on domain-owned gateways.",
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
    description="WARNING: This wil be rolled out slowly; do not enable on your own.",
)

WHATSAPP_MESSAGING = StaticToggle(
    'whatsapp_messaging',
    "Default SMS to send messages via Whatsapp, where available",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

UNLIMITED_REPORT_BUILDER_REPORTS = StaticToggle(
    'unlimited_report_builder_reports',
    'Allow unlimited reports created in report builder',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN]
)

SHOW_IDS_IN_REPORT_BUILDER = StaticToggle(
    'show_ids_in_report_builder',
    'Allow adding Case IDs to report builder reports.',
    TAG_SOLUTIONS_OPEN,
    [NAMESPACE_DOMAIN],
)


ALLOW_USER_DEFINED_EXPORT_COLUMNS = StaticToggle(
    'allow_user_defined_export_columns',
    'Add user defined columns to exports',
    TAG_DEPRECATED,
    [NAMESPACE_DOMAIN],
)

DISABLE_COLUMN_LIMIT_IN_UCR = StaticToggle(
    'disable_column_limit_in_ucr',
    'Enikshay: Disable column limit in UCR',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

OVERRIDE_EXPANDED_COLUMN_LIMIT_IN_REPORT_BUILDER = StaticToggle(
    'override_expanded_column_limit_in_report_builder',
    'USH: Override the limit for expanded columns in report builder from 10 to 50',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

CLOUDCARE_LATEST_BUILD = StaticToggle(
    'use_latest_build_cloudcare',
    'Uses latest build for Web Apps instead of latest published',
    TAG_SOLUTIONS_OPEN,
    [NAMESPACE_DOMAIN, NAMESPACE_USER]
)

CAUTIOUS_MULTIMEDIA = StaticToggle(
    'cautious_multimedia',
    'More cautious handling of multimedia: do not delete multimedia files, add logging, etc.',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
)

LOCALE_ID_INTEGRITY = StaticToggle(
    'locale_id_integrity',
    'Verify all locale ids in suite are present in app strings before allowing CCZ download',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    notification_emails=['jschweers']
)

BULK_UPDATE_MULTIMEDIA_PATHS = StaticToggle(
    'bulk_update_multimedia_paths',
    'Bulk multimedia path management',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/IndiaDivision/Multimedia+Path+Manager"
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
    'Disable submissions, restores, and web user access during a data migration',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN]
)

EMWF_WORKER_ACTIVITY_REPORT = StaticToggle(
    'emwf_worker_activity_report',
    'Make the Worker Activity Report use the Groups or Users or Locations filter',
    TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description=(
        "This flag allows you filter the users to display in the same way as the "
        "other reports - by individual user, group, or location.  Note that this "
        "will also force the report to always display by user."
    ),
)

SORT_CALCULATION_IN_CASE_LIST = StaticToggle(
    'sort_calculation_in_case_list',
    'Configure a custom xpath calculation for Sort Property in Case Lists',
    TAG_SOLUTIONS_CONDITIONAL,
    [NAMESPACE_DOMAIN]
)

PAGINATED_EXPORTS = StaticToggle(
    'paginated_exports',
    'Allows for pagination of exports for very large exports',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN]
)

CLEAR_MOBILE_WORKER_DATA = StaticToggle(
    'clear_mobile_worker_data',
    "Allows a web user to clear mobile workers' data",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

SKIP_REMOVE_INDICES = StaticToggle(
    'skip_remove_indices',
    'Make _remove_indices_from_deleted_cases_task into a no-op.',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN]
)

MOBILE_RECOVERY_MEASURES = StaticToggle(
    'mobile_recovery_measures',
    'Mobile recovery measures',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
    description=("Used for widely deployed projects where recovery from "
                 "large-scale failures would otherwise be next to impossible."),
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
    TAG_SOLUTIONS_OPEN,
    [NAMESPACE_DOMAIN]
)

BULK_UPLOAD_DATE_OPENED = StaticToggle(
    'bulk_upload_date_opened',
    "Allow updating of the date_opened field with the bulk uploader",
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
)

TWO_FACTOR_SUPERUSER_ROLLOUT = StaticToggle(
    'two_factor_superuser_rollout',
    'Users in this list will be forced to have Two-Factor Auth enabled',
    TAG_INTERNAL,
    [NAMESPACE_USER]
)

CUSTOM_ICON_BADGES = StaticToggle(
    'custom_icon_badges',
    'Custom Icon Badges for modules and forms',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
)

MULTI_MASTER_LINKED_DOMAINS = StaticToggle(
    'multi_master_linked_domains',
    "Allow linked apps to pull from multiple master apps in the upstream domain",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

SESSION_ENDPOINTS = StaticToggle(
    'session_endpoints',
    'Enable session endpoints',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN],
    description='Support external Android apps calling in to an endpoint in a '
                'CommCare app. (Used by the Reminders App)',
)

CASE_LIST_CLICKABLE_ICON = StaticToggle(
    'case_list_clickable_icon',
    'USH: Allow use of clickable icons in the case list in Web Apps to trigger auto submitting forms',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    parent_toggles=[SESSION_ENDPOINTS]
)

SUMOLOGIC_LOGS = DynamicallyPredictablyRandomToggle(
    'sumologic_logs',
    'Send logs to sumologic',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_OTHER],
)

TARGET_COMMCARE_FLAVOR = StaticToggle(
    'target_commcare_flavor',
    'Target CommCare Flavor.',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

TRAINING_MODULE = StaticToggle(
    'training-module',
    'Training Modules',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

APP_TRANSLATIONS_WITH_TRANSIFEX = StaticToggle(
    'app_trans_with_transifex',
    'Translate Application Content With Transifex',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER]
)

VALIDATE_APP_TRANSLATIONS = StaticToggle(
    'validate_app_translations',
    'Validate app translations before uploading them',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER]
)

AGGREGATE_UCRS = StaticToggle(
    'aggregate_ucrs',
    'Enable experimental aggregate UCR support',
    TAG_INTERNAL,  # this might change in the future
    namespaces=[NAMESPACE_DOMAIN],
    notification_emails=['czue'],
)

SHOW_RAW_DATA_SOURCES_IN_REPORT_BUILDER = StaticToggle(
    'show_raw_data_sources_in_report_builder',
    'Allow building report builder reports directly from raw UCR Data Sources',
    TAG_SOLUTIONS_CONDITIONAL,
    namespaces=[NAMESPACE_DOMAIN],
)

ALLOW_BLANK_CASE_TAGS = StaticToggle(
    'allow_blank_case_tags',
    'eCHIS/ICDS: Allow blank case tags',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

FILTER_ON_GROUPS_AND_LOCATIONS = StaticToggle(
    'filter_on_groups_and_locations',
    '[ONSE] Change filter from groups OR locations to groups AND locations in all reports and exports in the '
    'ONSE domain with group and location filters',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description='For reports filtered by groups and locations, change the OR logic to an AND, so that '
                '(for example): "Groups or Users: [Salima District] AND [User group Healthworkers]" '
                'returns 40 healthworkers who are also in salima. Changes this logic to all reports that '
                'have group and location filters, such as the Submissions by Form report.',
)

DONT_INDEX_SAME_CASETYPE = StaticToggle(
    'dont_index_same_casetype',
    "Don't create a parent index if the child case has the same case type as the parent case",
    TAG_DEPRECATED,
    namespaces=[NAMESPACE_DOMAIN],
    description=inspect.cleandoc("""This toggle preserves old behaviour
        of not creating a parent index on the child case if their case
        types are the same.""")
)

SORT_OUT_OF_ORDER_FORM_SUBMISSIONS_SQL = DynamicallyPredictablyRandomToggle(
    'sort_out_of_order_form_submissions_sql',
    'Sort out of order form submissions in the SQL update strategy',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
)


RELEASE_BUILDS_PER_PROFILE = StaticToggle(
    'release_builds_per_profile',
    'Do not release builds for all app profiles by default. Then manage via Source files view',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

MANAGE_RELEASES_PER_LOCATION = StaticToggle(
    'manage_releases_per_location',
    'Manage releases per location',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/Manage+Releases+per+Location',
)

HIDE_HQ_ON_MOBILE_EXPERIENCE = StaticToggle(
    'hide_hq_on_mobile_experience',
    'Do not show modal on mobile that mobile hq experience is bad',
    TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN]
)

COPY_CASES = StaticToggle(
    'copy_cases',
    'Enable users to copy cases between mobile workers',
    TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
)

DASHBOARD_REACH_REPORT = StaticToggle(
    'dashboard_reach_reports',
    'REACH: Enable access to the AAA Convergence Dashboard reports for REACH',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

PARTIAL_UI_TRANSLATIONS = StaticToggle(
    'partial_ui_translations',
    'Enable uploading a subset of translations in the UI Translations Excel upload',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

SKIP_ORM_FIXTURE_UPLOAD = StaticToggle(
    'skip_orm_fixture_upload',
    'Exposes an option in fixture api upload to skip saving through couchdbkit',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

ENABLE_UCR_MIRRORS = StaticToggle(
    'enable_ucr_mirrors',
    'Enable the mirrored engines for UCRs in this domain',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

LOCATION_COLUMNS_APP_STATUS_REPORT = StaticToggle(
    'location_columns_app_status_report',
    'Enables location columns to app status report',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

SKIP_CREATING_DEFAULT_BUILD_FILES_ON_BUILD = StaticToggle(
    'skip_creating_default_build_files_on_build',
    'Skips creating the build files for default profile each time a build is made'
    'which helps speed up the build and revert process',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

DISABLE_CASE_UPDATE_RULE_SCHEDULED_TASK = StaticToggle(
    'disable_case_update_rule_task',
    'Disable the `run_case_update_rules` periodic task '
    'while investigating database performance issues.',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

DO_NOT_RATE_LIMIT_SUBMISSIONS = StaticToggle(
    'do_not_rate_limit_submissions',
    'Do not rate limit submissions for this project, on a temporary basis.',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
    description="""
    When an individual project is having problems with rate limiting,
    use this toggle to lift the restriction for them on a temporary basis,
    just to unblock them while we sort out the conversation with the client.
    """
)

TEST_FORM_SUBMISSION_RATE_LIMIT_RESPONSE = StaticToggle(
    'test_form_submission_rate_limit_response',
    "Respond to all form submissions with a 429 response",
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    For use on test domains only.
    Without this, there's no sane way to test the UI for being rate limited on
    Mobile and Web Apps. Never use this on a real domain.
    """
)

RATE_LIMIT_RESTORES = DynamicallyPredictablyRandomToggle(
    'rate_limit_restores',
    'Rate limit restores with a 429 TOO MANY REQUESTS response',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
    description="""
    While we are gaining an understanding of the effects of rate limiting,
    we want to force rate limiting on certain domains, while also being to
    toggle on and off global rate limiting quickly in response to issues.

    To turn on global rate limiting, set Randomness Level to 1.
    To turn it off, set to 0.
    """
)

BLOCK_RESTORES = StaticToggle(
    'block_restores',
    'Block Restores Immediately with a 429 TOO MANY REQUESTS response',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
    description="""
    Use this flag for EMERGENCY PURPOSES ONLY if a project's restore is causing
    system-wide issues that aren't caught by rate limiting or other mechanisms.
    """
)

SKIP_FIXTURES_ON_RESTORE = StaticToggle(
    'skip_fixtures_on_restore',
    'Skip Fixture Syncs on Restores',
    TAG_INTERNAL,
    [NAMESPACE_DOMAIN],
    description="""
    Use this flag to skip fixtures on restores for certain project spaces.
    """
)

SKIP_UPDATING_USER_REPORTING_METADATA = StaticToggle(
    'skip_updating_user_reporting_metadata',
    'ICDS: Skip updates to user reporting metadata to avoid expected load on couch',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

DOMAIN_PERMISSIONS_MIRROR = StaticToggle(
    'domain_permissions_mirror',
    "USH: Enterprise Permissions: mirror a project space's permissions in other project spaces",
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/Enterprise+Permissions',
)

SHOW_BUILD_PROFILE_IN_APPLICATION_STATUS = StaticToggle(
    'show_build_profile_in_app_status',
    'Show build profile installed on phone tracked via heartbeat request in App Status Report',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

LIVEQUERY_READ_FROM_STANDBYS = DynamicallyPredictablyRandomToggle(
    'livequery_read_from_standbys',
    'Allow livequery restore to read data from plproxy standbys if they are available',
    TAG_INTERNAL,
    [NAMESPACE_USER],
    description="""
    To allow a gradual rollout and testing of using the standby
    databases to generate restore payloads.
    """
)

ACCOUNTING_TESTING_TOOLS = StaticToggle(
    'accounting_testing_tools',
    'Enable Accounting Testing Tools',
    TAG_INTERNAL,
    [NAMESPACE_USER]
)

ADD_ROW_INDEX_TO_MOBILE_UCRS = StaticToggle(
    'add_row_index_to_mobile_ucrs',
    'Add row index to mobile UCRs as the first column to retain original order of data',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN]
)

TWO_STAGE_USER_PROVISIONING = StaticToggle(
    'two_stage_user_provisioning',
    'Enable two-stage user provisioning (users confirm and set their own passwords via email).',
    TAG_SOLUTIONS_LIMITED,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/Two-Stage+Mobile+Worker+Account+Creation',
)

REFER_CASE_REPEATER = StaticToggle(
    'refer_case_repeater',
    'USH: Allow refer case repeaters to be setup',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/COVID%3A+Allow+refer+case+repeaters+to+be+setup",
)

WIDGET_DIALER = StaticToggle(
    'widget_dialer',
    'USH: Enable usage of AWS Connect Dialer',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/COVID%3A+Enable+usage+of+AWS+Connect+Dialer",
)

HMAC_CALLOUT = StaticToggle(
    'hmac_callout',
    'USH: Enable signed messaging url callouts in cloudcare',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/COVID%3A+Enable+signed+messaging+url+callouts+in+cloudcare",  # noqa: E501
)

GAEN_OTP_SERVER = StaticToggle(
    'gaen_otp_server',
    'USH: Enable retrieving OTPs from a GAEN Server',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/COVID%3A+Enable+retrieving+OTPs+from+a+GAEN+Server",
)

PARALLEL_USER_IMPORTS = StaticToggle(
    'parallel_user_imports',
    'USH: Process user imports in parallel on a dedicated queue',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/Parallel+User+Imports"
)

RESTRICT_LOGIN_AS = StaticToggle(
    'restrict_login_as',
    'USH: Limit allowed users for Log In As',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    Adds a permission that can be set on user roles to allow log in as, but only
    as a limited set of users. Users with this enabled can "log in as" other
    users that set custom user property "login_as_user" to the first user's
    username.

    For example, if web user a@a.com has this permission set on their role,
    they can only log in as mobile users who have the custom property
    "login_as_user" set to "a@a.com".
    """,
    help_link="https://confluence.dimagi.com/display/saas/Limited+Login+As",
)

ONE_PHONE_NUMBER_MULTIPLE_CONTACTS = StaticToggle(
    'one_phone_number_multiple_contacts',
    'Allow multiple contacts to share a single phone number',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    Allows multiple SMS contacts in a project space to share the same phone number.
    Sessions for different contacts are initiated in series rather than in parallel so that
    only one contact per phone number is in an active session at any given time.
    Incoming SMS are then routed to the live session.
    If a form goes unfilled over SMS, it will prevent any further forms (for that contact or another)
    from being initiated on that phone number until the original session expires.

    Only use this feature if every form behind an SMS survey begins by identifying the contact.
    Otherwise the recipient has no way to know who they're supposed to be enter information about.
    """,
    help_link="https://confluence.dimagi.com/display/saas/One+Phone+Number+-+Multiple+Contacts",
    parent_toggles=[INBOUND_SMS_LENIENCY]
)

BLOCKED_EMAIL_DOMAIN_RECIPIENTS = StaticToggle(
    'blocked_email_domain_recipients',
    'Block any outgoing email addresses that have an email domain which '
    'match a domain in this list.',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_EMAIL_DOMAIN],
)

BLOCKED_DOMAIN_EMAIL_SENDERS = StaticToggle(
    'blocked_domain_email_senders',
    'Domains in this list are blocked from sending emails through our '
    'messaging feature',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
)

ENTERPRISE_USER_MANAGEMENT = StaticToggle(
    'enterprise_user_management',
    'USH: UI for managing all web users in an enterprise',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_USER],
    help_link="https://confluence.dimagi.com/display/saas/USH%3A+UI+for+managing+all+web+users+in+an+enterprise",
)

CLEAN_OLD_FORMPLAYER_SYNCS = DynamicallyPredictablyRandomToggle(
    'clean_old_formplayer_syncs',
    'Delete old formplayer syncs during submission processing',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_OTHER],
    default_randomness=0.001
)

PRIME_FORMPLAYER_DBS = StaticToggle(
    'prime_formplayer_dbs',
    'USH: Control which domains will be included in the prime formplayer task runs',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/Prime+Formplayer+DBS"
)

FHIR_INTEGRATION = StaticToggle(
    'fhir_integration',
    'FHIR: Enable setting up FHIR integration',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/GS/FHIR+API+Documentation",
)

AUTO_DEACTIVATE_MOBILE_WORKERS = StaticToggle(
    'auto_deactivate_mobile_workers',
    'Development flag for auto-deactivation of mobile workers. To be replaced '
    'by a privilege.',
    TAG_PRODUCT,
    namespaces=[NAMESPACE_DOMAIN],
)

SSO_OIDC_DEVELOPMENT = StaticToggle(
    'sso_oidc_development',
    'Development feature flag for SSO OIDC support',
    TAG_PRODUCT,
    namespaces=[NAMESPACE_DOMAIN, NAMESPACE_USER],
)

ADD_LIMITED_FIXTURES_TO_CASE_RESTORE = StaticToggle(
    'fixtures_in_case_restore',
    'Allow limited fixtures to be available in case restore for SMS workflows.',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    WARNING: To be used only for small templates since the performance implication has not been evaluated.
    Do not enable on your own.
    """
)

EMBEDDED_TABLEAU = StaticToggle(
    'embedded_tableau',
    'USH: Enable retrieving and embedding tableau visualizations from a Tableau Server',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/USH/Embedded+Tableau+Visualizations",
)

DETAILED_TAGGING = StaticToggle(
    'detailed_tagging',
    'Send additional metrics to datadog and sentry.',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
)

HIGH_COUNT_DETAILED_TAGGING = StaticToggle(
    'HIGH_COUNT_DETAILED_TAGGING',
    'Send additional metrics to datadog and sentry. These tags have a high number of combinations.',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
)

USER_HISTORY_REPORT = StaticToggle(
    'user_history_report',
    'View user history report under user management',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_USER],
    help_link="https://confluence.dimagi.com/display/saas/User+History+Report",
)


COWIN_INTEGRATION = StaticToggle(
    'cowin_integration',
    'Integrate with COWIN APIs',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

EXPRESSION_REPEATER = StaticToggle(
    'expression_repeater',
    'Integrate with generic APIs using UCR expressions',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/Configurable+Repeaters",
)

UCR_EXPRESSION_REGISTRY = StaticToggle(
    'expression_registry',
    'Store named UCR expressions and filters in the database to be referenced elsewhere',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/UCR+Expression+Registry",
)

GENERIC_INBOUND_API = StaticToggle(
    'configurable_api',
    'Generic inbound APIs',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    description="Create inbound APIs that use UCR expressions to process data into case updates",
    help_link="https://docs.google.com/document/d/1y9CZwpzGYtitxbh-Y7nS5-WoMUg-LbRlZHd-eD5i78U/edit",
    parent_toggles=[UCR_EXPRESSION_REGISTRY]
)

CASE_UPDATES_UCR_FILTERS = StaticToggle(
    'case_updates_ucr_filters',
    'Allow the use of UCR filters in Auto Case Update Rules',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
)

TURN_IO_BACKEND = StaticToggle(
    'turn_io_backend',
    'Enable Turn.io SMS backend',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
)

FOLLOWUP_FORMS_AS_CASE_LIST_FORM = StaticToggle(
    'followup_forms_as_case_list_form',
    'Option to configure follow up forms on parent case for Case List Form menu setting of '
    'child modules that use Parent Child Selection',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/pages/viewpage.action?spaceKey=USH&title=Add+Form+to+Bottom+of++Case+List",  # noqa: E501
)


DATA_REGISTRY = StaticToggle(
    'data_registry',
    'USH: Enable Data Registries for sharing data between project spaces',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/USH/Data+Registry",
)

DATA_REGISTRY_UCR = StaticToggle(
    'data_registry_ucr',
    'USH: Enable the creation of Custom Web Reports backed by Data Registries',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/USH/Data+Registry#DataRegistry-CrossDomainReports",
    parent_toggles=[DATA_REGISTRY]
)

DATA_REGISTRY_CASE_UPDATE_REPEATER = StaticToggle(
    'data_registry_case_update_repeater',
    'USH: Allow data registry repeater to be setup to update cases in other domains',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/USH/Data+Registry+Case+Update+Repeater",
    parent_toggles=[DATA_REGISTRY]
)

CASE_IMPORT_DATA_DICTIONARY_VALIDATION = StaticToggle(
    'case_import_data_dictionary_validaton',
    'USH: Validate data per data dictionary definitions during case import',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    help_link="https://confluence.dimagi.com/display/saas/Validate+data+per+data+dictionary+definitions+during+case+import",  # noqa: E501
)

DO_NOT_REPUBLISH_DOCS = StaticToggle(
    'do_not_republish_docs',
    'Prevents automatic attempts to repair stale ES docs in this domain',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
)

HOURLY_SCHEDULED_REPORT = StaticToggle(
    'hourly-scheduled-report',
    'Add ability to send a scheduled report hourly',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
)

SUPPORT_EXPANDED_COLUMN_IN_REPORTS = StaticToggle(
    'support_expanded_column_in_reports',
    'Support count per choice column to show up in multibar graph in reports',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN]
)

SAVE_ONLY_EDITED_FORM_FIELDS = FeatureRelease(
    'save-only-edited-form-fields',
    'Save a form field only if the answer has been edited',
    TAG_RELEASE,
    namespaces=[NAMESPACE_DOMAIN],
    owner='Addison Dunn',
    description="""
    Enable a checkbox for the ability to save a form question's answer in Case Management in App
    Manager only if the question's inputted answer is different from the current value in the case.
    """
)

GOOGLE_SHEETS_INTEGRATION = StaticToggle(
    'google-sheet-integration',
    'Unlock the Google Sheets view in Exports',
    TAG_SAAS_CONDITIONAL,
    namespaces=[NAMESPACE_USER],
    description="""
    Toggle only when testing the new Google Sheet Integration. The Google Sheet Integration can be found
    on the Exports page.
    """
)

APP_DEPENDENCIES = StaticToggle(
    'app-dependencies',
    'Set Android app dependencies that must be installed before using a '
    'CommCare app',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    Prevents mobile workers from using a CommCare app until the Android apps
    that it needs have been installed on the device.
    """,
)

SUPERSET_ANALYTICS = StaticToggle(
    'superset-analytics',
    'Activates Analytics features to create Superset based reports and dashboards using UCR data',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
)

TWO_STAGE_USER_PROVISIONING_BY_SMS = StaticToggle(
    'two_stage_user_provisioning_by_sms',
    'Enable two-stage user provisioning (users confirm and set their own passwords via sms).',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

SMS_USE_LATEST_DEV_APP = FeatureRelease(
    'sms_use_latest_dev_app',
    'Use latest development version of the app for SMS processing',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
    owner='Simon Kelly',
    description='This will revert the SMS processing to previous functionality of using the '
                'development version of the app instead of the latest release. It should only'
                'be used temporarily if a domain needs unreleased app changes to be used for SMS.',
)

VIEW_FORM_ATTACHMENT = StaticToggle(
    'view_form_attachments',
    'Allow users on the domain to view form attachments without having to have the report Submit History permission.',  # noqa: E501
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)


DISABLE_FORM_ATTACHMENT_DOWNLOAD_IN_BROWSER = StaticToggle(
    'disable_form_attachment_download_in_browser',
    'Restrict users from downloading audio/video form attachments in browser',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN]
)


FORMPLAYER_INCLUDE_STATE_HASH = FeatureRelease(
    'formplayer_include_state_hash',
    'Make Formplayer include the state hash in sync and restore requests',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
    owner='Simon Kelly'
)

EMBED_TABLEAU_REPORT_BY_USER = StaticToggle(
    'embed_tableau_report_by_user',
    'Use a Tableau username "HQ/{username}" to embed reports instead of "HQ/{role name}"',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
    description='By default, a Tableau username "HQ/{role name}" is sent to Tableau to get the embedded report. '
                'Turn on this flag to instead send "HQ/{the user\'s HQ username}", i.e. "HQ/jdoe@dimagi.com", '
                'to Tableau to get the embedded report.',
    parent_toggles=[EMBEDDED_TABLEAU]
)

APPLICATION_RELEASE_LOGS = StaticToggle(
    'application_release_logs',
    'Show Application release logs',
    TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description='This feature provides the release logs for application.'
)

TABLEAU_USER_SYNCING = StaticToggle(
    'tableau_user_syncing',
    'Automatically sync HQ users with users on Tableau',
    TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    Each time a user is added/deleted/updated on HQ, an equivalent Tableau user with the username "HQ/{username}"
    will be added/deleted/updated on the linked Tableau server.
    """,
    parent_toggles=[EMBED_TABLEAU_REPORT_BY_USER],
    help_link='https://confluence.dimagi.com/display/USH/Tableau+User+Syncing',
)


def _handle_attendance_tracking_role(domain, is_enabled):
    from corehq.apps.accounting.utils import domain_has_privilege
    from corehq.apps.users.role_utils import (
        archive_attendance_coordinator_role_for_domain,
        enable_attendance_coordinator_role_for_domain,
    )

    if not domain_has_privilege(domain, privileges.ATTENDANCE_TRACKING):
        return

    if is_enabled:
        enable_attendance_coordinator_role_for_domain(domain)
    else:
        archive_attendance_coordinator_role_for_domain(domain)


ATTENDANCE_TRACKING = StaticToggle(
    'attendance_tracking',
    'Allows access to the attendance tracking page',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    description='Additional views will be added to simplify the process of '
                'using CommCare HQ for attendance tracking.',
    save_fn=_handle_attendance_tracking_role,
)

GEOSPATIAL = StaticToggle(
    'geospatial',
    'Allows access to GIS functionality',
    TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    description='Additional views will be added allowing for visually viewing '
                'and assigning cases on a map.'

)

COMMCARE_CONNECT = StaticToggle(
    'commcare_connect',
    'Enable CommCare Connect features',
    tag=TAG_INTERNAL,
    namespaces=[NAMESPACE_DOMAIN],
    description='More details to come',

)

FCM_NOTIFICATION = StaticToggle(
    'fcm_notification',
    'Allows access to FCM Push Notifications',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description='Push Notification option will be available in content for '
                'Conditional Alerts in Messaging.'
)

SHOW_OWNER_LOCATION_PROPERTY_IN_REPORT_BUILDER_TOGGLE = StaticToggle(
    'show_owner_location_property_in_report_builder',
    label='Show an additional "Owner (Location)" property in report builder reports.',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/Enable+creation+of+report+builder+reports+that+are+location+safe',  # noqa: E501
    description='This can be used to create report builder reports that are location-safe.'
)

LOCATION_RESTRICTED_SCHEDULED_REPORTS = StaticToggle(
    'location_restricted_scheduled_reports',
    'Allows access to report scheduling views for location restricted users',
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description='Provides access to views for report scheduling '
                'such as schedule creation and deletion.'
)

CUSTOM_EMAIL_GATEWAY = StaticToggle(
    'custom_email_gateway',
    'Allows user to define custom email gateway that can be used to send emails from HQ',
    TAG_CUSTOM,
    [NAMESPACE_DOMAIN],
    help_link=('https://confluence.dimagi.com/display/USH/'
               'Allow+user+to+define+custom+email+gateway+that+'
               'can+be+used+to+send+emails+from+HQ'),
)

ALLOW_WEB_APPS_RESTRICTION = StaticToggle(
    'allow_web_apps_restriction',
    'Makes domain eligible to be restricted from using web apps/app preview.',
    tag=TAG_SAAS_CONDITIONAL,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
    When enabled, the domain is eligible to be restricted from using web apps/app preview. The intention is
    to only enable this for domains in extreme cases where their formplayer restores are resource intensive
    to the point where they can degrade web apps performance for the entire system.
    """
)


class FrozenPrivilegeToggle(StaticToggle):
    """
    A special toggle to represent a legacy toggle that should't be
    edited via the UI or the code and its new associated privilege.

    This can be used when releasing a domain-only Toggle to general
    availability as a new paid privilege to support domains that
    may not have the privilege but had the toggle enabled historically.

    To do this, simply change the toggle type to FrozenPrivilegeToggle
    and pass the privilege as the first argument to it.

    For e.g.
    If a toggle were defined as below
        MY_DOMAIN_TOGGLE = StaticToggle(
            'toggle_name',
            'Title',
            TAG_PRODUCT,
            namespaces=[NAMESPACE_DOMAIN],
            description='Description'
        )
    It can be converted to a FrozenPrivilegeToggle by defining.
        MY_DOMAIN_TOGGLE = FrozenPrivilegeToggle(
            privilege_name
            'toggle_name',
            'Title',
            TAG_PRODUCT,
            namespaces=[NAMESPACE_DOMAIN],
            description='Description'
        )
    """

    def __init__(self, privilege_slug, *args, **kwargs):
        self.privilege_slug = privilege_slug
        super(FrozenPrivilegeToggle, self).__init__(*args, **kwargs)


def frozen_toggles_by_privilege():
    return {
        t.privilege_slug: t
        for t in all_toggles_by_name_in_scope(globals(), FrozenPrivilegeToggle).values()
    }


def domain_has_privilege_from_toggle(privilege_slug, domain):
    toggle = frozen_toggles_by_privilege().get(privilege_slug)
    return toggle and toggle.enabled(domain)


FORM_LINK_WORKFLOW = FrozenPrivilegeToggle(
    privileges.FORM_LINK_WORKFLOW,
    'form_link_workflow',
    'Form linking workflow available on forms',
    TAG_SOLUTIONS_CONDITIONAL,
    [NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/Form+Link+Workflow+Feature+Flag',
)

PHONE_HEARTBEAT = FrozenPrivilegeToggle(
    privileges.PHONE_APK_HEARTBEAT,
    'phone_apk_heartbeat',
    "Ability to configure a mobile feature to prompt users to update to latest CommCare app and apk",
    TAG_SOLUTIONS_CONDITIONAL,
    [NAMESPACE_DOMAIN]
)


MOBILE_USER_DEMO_MODE = FrozenPrivilegeToggle(
    privileges.PRACTICE_MOBILE_WORKERS,
    'mobile_user_demo_mode',
    'Ability to make a mobile worker into Demo only mobile worker',
    TAG_SOLUTIONS_OPEN,
    help_link='https://confluence.dimagi.com/display/GS/Demo+Mobile+Workers+and+Practice+Mode',
    namespaces=[NAMESPACE_DOMAIN]
)


VIEW_APP_CHANGES = FrozenPrivilegeToggle(
    privileges.VIEW_APP_DIFF,
    'app-changes-with-improved-diff',
    'Improved app changes view',
    TAG_SOLUTIONS_OPEN,
    [NAMESPACE_DOMAIN, NAMESPACE_USER],
    help_link="https://confluence.dimagi.com/display/saas/Viewing+App+Changes+between+versions",
)


CASE_LIST_EXPLORER = FrozenPrivilegeToggle(
    privileges.CASE_LIST_EXPLORER,
    'case_list_explorer',
    label='Show the case list explorer report',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    save_fn=_ensure_search_index_is_enabled,
    help_link='https://confluence.dimagi.com/display/commcarepublic/Case+List+Explorer',
)


DATA_FILE_DOWNLOAD = FrozenPrivilegeToggle(
    privileges.DATA_FILE_DOWNLOAD,
    'data_file_download',
    label='Offer hosting and sharing data files for downloading from a secure '
          'dropzone',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/Offer+hosting+and+'
              'sharing+data+files+for+downloading+from+a+secure+dropzone',
)

REGEX_FIELD_VALIDATION = FrozenPrivilegeToggle(
    privileges.REGEX_FIELD_VALIDATION,
    'regex_field_validation',
    label='Regular Expression Validation for Custom Data Fields',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description="This flag adds the option to specify a regular expression "
                "(regex) to validate custom user data, custom location data, "
                "and/or custom product data fields.",
    help_link='https://confluence.dimagi.com/display/saas/Regular+Expression+Validation+for+Custom+Data+Fields',
)

LOCATION_SAFE_CASE_IMPORTS = FrozenPrivilegeToggle(
    privileges.LOCATION_SAFE_CASE_IMPORTS,
    'location_safe_case_imports',
    label='Location-restricted users can import cases at their location or below',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description='Allow location-restricted users to import cases owned at their location or below',
)

FORM_CASE_IDS_CASE_IMPORTER = FrozenPrivilegeToggle(
    privileges.FORM_CASE_IDS_CASE_IMPORTER,
    'form_case_ids_case_importer',
    label='Download buttons for Form- and Case IDs on Case Importer',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description='Display the "Form IDs" and "Case IDs" download buttons on Case Importer',
)

EXPORT_MULTISORT = FrozenPrivilegeToggle(
    privileges.EXPORT_MULTISORT,
    'export_multisort',
    label='Sort multiple rows in exports simultaneously',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description='Sort multiple rows in exports simultaneously',
)

EXPORT_OWNERSHIP = FrozenPrivilegeToggle(
    privileges.EXPORT_OWNERSHIP,
    'export_ownership',
    label='Allow exports to have ownership',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description='Allow exports to have ownership',
)

FORCE_ANNUAL_TOS = StaticToggle(
    'annual_terms_of_service',
    "USH Specific toggle that forces users to agree to terms of service annually.",
    TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
)

FILTERED_BULK_USER_DOWNLOAD = FrozenPrivilegeToggle(
    privileges.FILTERED_BULK_USER_DOWNLOAD,
    'filtered_bulk_user_download',
    label='Bulk user management features',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description="""
        For mobile users, enables bulk deletion page and bulk lookup page.
        For web users, enables filtered download page.
    """,
    help_link='https://confluence.dimagi.com/display/commcarepublic/Bulk+User+Management'
)

APPLICATION_ERROR_REPORT = FrozenPrivilegeToggle(
    privileges.APPLICATION_ERROR_REPORT,
    'application_error_report',
    label='Show Application Error Report',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description="Show Application Error Report.",
    # TODO: Move to public wiki
    help_link='https://confluence.dimagi.com/display/saas/Show+Application+Error+Report+Feature+Flag'
)

DATA_DICTIONARY = FrozenPrivilegeToggle(
    privileges.DATA_DICTIONARY,
    'data_dictionary',
    label='Project level data dictionary of cases',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description='Project level data dictionary of cases',
    help_link='https://confluence.dimagi.com/display/commcarepublic/Data+Dictionary'
)

CASE_DEDUPE = FrozenPrivilegeToggle(
    privileges.CASE_DEDUPE,
    'case_dedupe',
    label='Case deduplication feature',
    tag=TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    help_link='https://confluence.dimagi.com/display/saas/Surfacing+Case+Duplicates+in+CommCare',
)

USE_LOGO_IN_SYSTEM_EMAILS = StaticToggle(
    slug='use_logo_in_system_emails',
    label='Use the project\'s logo in emails sent from HQ',
    tag=TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description='The project logo replaces the CommCare logo.',
)

VELLUM_CASE_MICRO_IMAGE = StaticToggle(
    slug='case_micro_image',
    label='Add case micro images to case list',
    tag=TAG_SOLUTIONS_LIMITED,
    namespaces=[NAMESPACE_DOMAIN],
    description='Add a micro image to cases in the case list.'
)

SUPPORT_GEO_JSON_EXPORT = StaticToggle(
    slug='support_geo_json_export',
    label='Support GeoJSON export in Case Exporter',
    tag=TAG_SOLUTIONS_CONDITIONAL,
    namespaces=[NAMESPACE_DOMAIN],
    description='The Case Export page now supports the exporting of GeoJSON data.',
)

USE_PROMINENT_PROGRESS_BAR = StaticToggle(
    slug='use_prominent_progress_bar',
    label='Use more prominent progress bar in place of NProgress',
    tag=TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description='Replaces NProgress bar with more prominent progress bar',
)

INCREASED_MAX_SEARCH_RESULTS = StaticToggle(
    slug='increased_max_search_results',
    label='Increases the maximum number of Elasticsearch results from 500 to 1500',
    tag=TAG_CUSTOM,
    namespaces=[NAMESPACE_DOMAIN],
    description='Temporary increase of the max number of search results.',
)


SUPPORT_ROAD_NETWORK_DISBURSEMENT_ALGORITHM = StaticToggle(
    slug='support_road_network_disbursement_algorithm',
    label='Add Road Network disbursement algorithm on geospatial settings page',
    tag=TAG_SOLUTIONS_OPEN,
    namespaces=[NAMESPACE_DOMAIN],
    description='Add support for the Road Network disbursement algorithm for the Geospatial feature',
)
