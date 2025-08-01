from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop

from memoized import memoized

from corehq.feature_previews import USE_LOCATION_DISPLAY_NAME
from corehq.apps.domain.models import Domain
from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.apps.es import filters
from corehq.apps.es import users as user_es
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.extension_points import customize_user_query
from corehq.apps.user_importer.models import UserUploadRecord
from corehq.apps.users.cases import get_wrapped_owner
from corehq.apps.users.models import CommCareUser, UserHistory, WebUser
from corehq.apps.users.util import cached_user_id_to_user_display
from corehq.const import USER_DATETIME_FORMAT
from corehq.util.global_request import get_request_domain
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_user

from .. import util
from ..analytics.esaccessors import get_group_stubs, get_user_stubs
from ..models import HQUserType
from .base import (
    BaseMultipleOptionFilter,
    BaseReportFilter,
    BaseSingleOptionFilter,
)
from ..util import DatatablesServerSideParams


class UserOrGroupFilter(BaseSingleOptionFilter):
    slug = "view_by"
    label = gettext_lazy("View by Users or Groups")
    default_text = gettext_lazy("Users")
    options = [('groups', gettext_lazy('Groups'))]


class UserTypeFilter(BaseReportFilter):
    # note, don't use this as a guideline for anything.
    slug = "ufilter"
    label = gettext_lazy("User Type")
    template = "reports/filters/bootstrap3/filter_users.html"

    @property
    def filter_context(self):
        toggle, show_filter = self.get_user_filter(self.request)
        return {
            'show_user_filter': show_filter,
            'toggle_users': toggle,
        }

    @classmethod
    def get_user_filter(cls, request):
        return get_user_toggle(request)


class SelectMobileWorkerFilter(BaseSingleOptionFilter):
    slug = 'individual'
    label = gettext_lazy("Select Mobile Worker")
    default_text = gettext_lazy("All Mobile Workers")

    @property
    def filter_context(self):
        user_filter, _ = UserTypeFilter.get_user_filter(self.request)
        context = super(SelectMobileWorkerFilter, self).filter_context
        context['select'].update({
            'default_text': self.get_default_text(user_filter),
        })
        return context

    @property
    def options(self):
        users = util.user_list(self.domain)
        return [(user.user_id,
                 "%s%s" % (user.username_in_report, "" if user.is_active else " (Inactive)"))
                for user in users]

    @classmethod
    def get_default_text(cls, user_filter):
        default = cls.default_text
        if user_filter[HQUserType.ADMIN].show or \
           user_filter[HQUserType.DEMO_USER].show or user_filter[HQUserType.UNKNOWN].show:
            default = _('%s & Others') % _(default)
        return default


class BaseGroupedMobileWorkerFilter(BaseSingleOptionFilter):
    """
        This is a little field for use when a client really wants to filter by
        individuals from a specific group.  Since by default we still want to
        show all the data, no filtering is done unless the special group filter
        is selected.
    """
    group_names = []

    @property
    def options(self):
        options = []
        for group_name in self.group_names:
            group = Group.by_name(self.domain, group_name)
            if group:
                users = group.get_users(is_active=True, only_commcare=True)
                options.extend([(u.user_id, u.username_in_report) for u in users])
        return options


class EmwfUtils(object):
    def __init__(self, domain, namespace_locations=True):
        self.domain = domain
        self.namespace_locations = namespace_locations

    def user_tuple(self, u):
        user = util._report_user(u)
        uid = "u__%s" % user.user_id
        is_active = False
        if u['doc_type'] == 'WebUser':
            if WebUser.get_by_user_id(user.user_id).is_active_in_domain(self.domain):
                name = "%s [Active Web User]" % user.username_in_report
            else:
                name = "%s [Deactivated Web User]" % user.username_in_report
        elif user.is_active:
            is_active = True
            name = "%s [Active Mobile Worker]" % user.username_in_report
        else:
            name = "%s [Deactivated Mobile Worker]" % user.username_in_report
        return uid, name, is_active

    def reporting_group_tuple(self, g):
        return "g__%s" % g['_id'], '%s [group]' % g['name']

    def user_type_tuple(self, t):
        return (
            "t__%s" % t,
            "[%s]" % HQUserType.human_readable[t]
        )

    def location_tuple(self, location):
        location_id = location.location_id
        use_location_display_name = USE_LOCATION_DISPLAY_NAME.enabled(get_request_domain())
        text = location.display_name if use_location_display_name else location.get_path_display()
        tooltip = location.get_path_display() if use_location_display_name else location.display_name
        if self.namespace_locations:
            location_id = f'l__{location_id}'
            text = f'{text} [location]'
        return (location_id, text, None, tooltip)

    @property
    @memoized
    def static_options(self):
        types = ['ACTIVE', 'DEACTIVATED', 'DEMO_USER', 'ADMIN', 'WEB', 'DEACTIVATED_WEB', 'UNKNOWN']
        if Domain.get_by_name(self.domain).commtrack_enabled:
            types.append('COMMTRACK')
        return [self.user_type_tuple(getattr(HQUserType, t)) for t in types]

    def _group_to_choice_tuple(self, group):
        return self.reporting_group_tuple(group)

    def id_to_choice_tuple(self, id_):
        for static_id, text in self.static_options:
            if (id_ == static_id[3:] and static_id[:3] == "t__") or id_ == static_id:
                return (static_id, text)

        owner = get_wrapped_owner(id_, support_deleted=True)
        if isinstance(owner, Group):
            ret = self._group_to_choice_tuple(owner)
        elif isinstance(owner, SQLLocation):
            ret = self.location_tuple(owner)
        elif isinstance(owner, (CommCareUser, WebUser)):
            ret = self.user_tuple(owner)
        elif owner is None:
            return None
        else:
            raise Exception("Unexpcted id: {}".format(id_))

        if hasattr(owner, 'is_deleted'):
            if (callable(owner.is_deleted) and owner.is_deleted()) or owner.is_deleted:
                # is_deleted may be an attr or callable depending on owner type
                ret = (ret[0], 'Deleted - ' + ret[1])

        return ret


class UsersUtils(EmwfUtils):

    def user_tuple(self, u):
        user = util._report_user(u)
        uid = "%s" % user.user_id
        name = "%s" % user.username_in_report
        return (uid, name)


class ExpandedMobileWorkerFilter(BaseMultipleOptionFilter):
    """
    To get raw filter results:
        mobile_user_and_group_slugs = DatatablesServerSideParams.get_value_from_request(
            request, ExpandedMobileWorkerFilter.slug, as_list=True
        )

        user_ids = emwf.selected_user_ids(mobile_user_and_group_slugs)
        user_types = emwf.selected_user_types(mobile_user_and_group_slugs)
        group_ids = emwf.selected_group_ids(mobile_user_and_group_slugs)
    """
    location_search_help = mark_safe(gettext_lazy(  # nosec: no user input
        'When searching by location, put your location name in quotes to show only exact matches. '
        'To more easily find a location, you may specify multiple levels by separating with a "/". '
        'For example, "Massachusetts/Suffolk/Boston". '
        '<a href="https://dimagi.atlassian.net/wiki/spaces/'
        'commcarepublic/pages/2215051298/Organization+Data+Management#Search-for-Locations"'
        'target="_blank">Learn more</a>.'
    ))

    slug = "emw"
    label = gettext_lazy("User(s)")
    default_options = None
    placeholder = gettext_lazy("Add users and groups to filter this report.")
    is_cacheable = False
    options_url = 'emwf_options_all_users'
    filter_help_inline = mark_safe(gettext_lazy(  # nosec: no user input
        '<i class="fa fa-info-circle"></i> See '
        '<a href="https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143947350/Report+and+Export+Filters"'  # noqa: E501
        'target="_blank"> Filter Definitions</a>.'))

    @property
    @memoized
    def utils(self):
        return EmwfUtils(self.domain)

    @staticmethod
    def selected_user_ids(mobile_user_and_group_slugs):
        return [u[3:] for u in mobile_user_and_group_slugs if u.startswith("u__")]

    @staticmethod
    def selected_user_types(mobile_user_and_group_slugs):
        """
        usage: ``HQUserType.DEMO_USER in selected_user_types``
        """
        return [int(t[3:]) for t in mobile_user_and_group_slugs
                if t.startswith("t__") and t[3:].isdigit()]

    @classmethod
    def selected_group_ids(cls, mobile_user_and_group_slugs):
        return cls.selected_reporting_group_ids(mobile_user_and_group_slugs)

    @staticmethod
    def selected_reporting_group_ids(mobile_user_and_group_slugs):
        return [grp[3:] for grp in mobile_user_and_group_slugs
                if grp.startswith("g__")]

    @staticmethod
    def selected_location_ids(mobile_user_and_group_slugs):
        return [loc[3:] for loc in mobile_user_and_group_slugs
                if loc.startswith("l__")]

    @staticmethod
    def show_all_mobile_workers(mobile_user_and_group_slugs):
        return 't__0' in mobile_user_and_group_slugs

    @staticmethod
    def no_filters_selected(mobile_user_and_group_slugs):
        return not any(mobile_user_and_group_slugs)

    def _get_assigned_locations_default(self):
        user_locations = self.request.couch_user.get_sql_locations(self.domain)
        return list(map(self.utils.location_tuple, user_locations))

    def get_default_selections(self):
        if not self.request.can_access_all_locations:
            return self._get_assigned_locations_default()

        defaults = [
            self.utils.user_type_tuple(HQUserType.ACTIVE),
            self.utils.user_type_tuple(HQUserType.DEACTIVATED),
            self.utils.user_type_tuple(HQUserType.WEB),
            self.utils.user_type_tuple(HQUserType.DEACTIVATED_WEB)
        ]

        if self.request.project.commtrack_enabled:
            defaults.append(self.utils.user_type_tuple(HQUserType.COMMTRACK))
        return defaults

    @property
    @memoized
    def selected(self):
        selected_ids = DatatablesServerSideParams.get_value_from_request(
            self.request, self.slug, as_list=True
        )
        return self._get_selected_from_selected_ids(selected_ids)

    def _get_selected_from_selected_ids(self, selected_ids):
        if not selected_ids:
            return [{'id': selection_tuple[0], 'text': selection_tuple[1]}
                    for selection_tuple in self.get_default_selections()]

        selected = (self.selected_static_options(selected_ids)
                    + self._selected_user_entries(selected_ids)
                    + self._selected_group_entries(selected_ids)
                    + self._selected_location_entries(selected_ids))
        return [
            {'id': entry[0], 'text': entry[1]} if len(entry) == 2 else
            {'id': entry[0], 'text': entry[1], 'is_active': entry[2]} for entry in selected
        ]

    def selected_static_options(self, mobile_user_and_group_slugs):
        return [option for option in self.utils.static_options
                if option[0] in mobile_user_and_group_slugs]

    def _selected_user_entries(self, mobile_user_and_group_slugs):
        user_ids = self.selected_user_ids(mobile_user_and_group_slugs)
        if not user_ids:
            return []
        results = get_user_stubs(user_ids)
        return [self.utils.user_tuple(hit) for hit in results]

    def _selected_groups_query(self, mobile_user_and_group_slugs):
        group_ids = self.selected_group_ids(mobile_user_and_group_slugs)
        if not group_ids:
            return []
        return get_group_stubs(group_ids)

    def _selected_group_entries(self, mobile_user_and_group_slugs):
        groups = self._selected_groups_query(mobile_user_and_group_slugs)
        return [self.utils.reporting_group_tuple(group)
                for group in groups
                if group.get("reporting", False)]

    def _selected_location_entries(self, mobile_user_and_group_slugs):
        location_ids = self.selected_location_ids(mobile_user_and_group_slugs)
        if not location_ids:
            return []
        return list(map(self.utils.location_tuple,
                        SQLLocation.objects.filter(location_id__in=location_ids)))

    @property
    def filter_context(self):
        context = super(ExpandedMobileWorkerFilter, self).filter_context
        url = reverse(self.options_url, args=[self.domain])
        context.update({'endpoint': url})
        context.update({'filter_help_inline': self.filter_help_inline})
        if self.request.project.uses_locations:
            context.update({'search_help_inline': self.location_search_help})
        return context

    @classmethod
    def user_es_query(cls, domain, mobile_user_and_group_slugs, request_user):
        # The queryset returned by this method is location-safe
        es_domains = cls._es_query_domains(domain, request_user)
        q = user_es.UserES().domain(es_domains, include_inactive=True)
        q = customize_user_query(request_user, domain, q)
        if not request_user.has_permission(domain, 'access_all_locations'):
            q = q.location(list(
                SQLLocation.objects
                .accessible_to_user(domain, request_user)
                .location_ids()
            ))
        if ExpandedMobileWorkerFilter.no_filters_selected(mobile_user_and_group_slugs):
            return q

        user_ids = cls.selected_user_ids(mobile_user_and_group_slugs)
        user_types = cls.selected_user_types(mobile_user_and_group_slugs)
        group_ids = cls.selected_group_ids(mobile_user_and_group_slugs)
        location_ids = cls.selected_location_ids(mobile_user_and_group_slugs)

        user_type_filters = []
        has_user_ids = bool(user_ids)

        if HQUserType.ACTIVE in user_types or HQUserType.DEACTIVATED in user_types:
            user_type_filters.append(filters.AND(
                user_es.mobile_users(),
                user_es.domain(
                    es_domains,
                    include_active=(HQUserType.ACTIVE in user_types),
                    include_inactive=(HQUserType.DEACTIVATED in user_types),
                ),
            ))
        if HQUserType.ADMIN in user_types:
            user_type_filters.append(user_es.admin_users())
        if HQUserType.UNKNOWN in user_types:
            user_type_filters.append(user_es.unknown_users())
        if HQUserType.WEB in user_types or HQUserType.DEACTIVATED_WEB in user_types:
            user_type_filters.append(filters.AND(
                user_es.web_users(),
                user_es.domain(
                    es_domains,
                    include_active=HQUserType.WEB in user_types,
                    include_inactive=HQUserType.DEACTIVATED_WEB in user_types
                ),
            ))
        if HQUserType.DEMO_USER in user_types:
            user_type_filters.append(user_es.demo_users())

        if HQUserType.ACTIVE in user_types or HQUserType.DEACTIVATED in user_types:
            if has_user_ids:
                return q.OR(*user_type_filters, filters.OR(filters.term("_id", user_ids)))
            else:
                return q.OR(*user_type_filters)

        # return matching user types and exact matches
        location_query = SQLLocation.active_objects.get_locations_and_children(location_ids)
        if not request_user.has_permission(domain, 'access_all_locations'):
            location_query = location_query.accessible_to_user(domain, request_user)
        location_ids = list(location_query.location_ids())

        id_filter = filters.OR(
            filters.term("_id", user_ids),
            filters.AND(
                user_es.is_active(domain),
                filters.OR(
                    filters.term("__group_ids", group_ids),
                    user_es.location(location_ids),
                )
            ),
        )

        if user_type_filters:
            return q.OR(
                id_filter,
                filters.OR(*user_type_filters),
            )
        return q.filter(id_filter)

    @classmethod
    def _es_query_domains(cls, domain, request_user):
        domains = [domain] if isinstance(domain, str) else domain
        domains += list(cls._get_enterprise_domains(domains))
        return domains

    @classmethod
    def _get_enterprise_domains(cls, domains):
        from corehq.apps.enterprise.models import EnterprisePermissions
        for domain in domains:
            source_domain = EnterprisePermissions.get_source_domain(domain)
            if source_domain:
                yield source_domain

    @property
    def options(self):
        return [self.utils.user_type_tuple(HQUserType.ACTIVE)]

    @classmethod
    def for_user(cls, user_id):
        return {
            cls.slug: 'u__%s' % user_id
        }

    @classmethod
    def for_reporting_group(cls, group_id):
        return {
            cls.slug: 'g__%s' % group_id
        }

    @classmethod
    def for_reporting_location(cls, loc_id):
        return {
            cls.slug: 'l__%s' % loc_id
        }


class SubmittedByExpandedMobileWorkerFilter(ExpandedMobileWorkerFilter):
    label = gettext_lazy("Submitted By")


class EnterpriseUsersUtils(EmwfUtils):

    def user_tuple(self, user):
        user_obj = util._report_user(user)
        uid = "u__%s" % user_obj.user_id
        is_active = False
        report_username = user_obj.username_in_report
        if user['doc_type'] == 'WebUser':
            if WebUser.get_by_user_id(user_obj.user_id).is_active_in_domain(self.domain):
                name = f"{report_username} [Active Web User]"
            else:
                name = f"{report_username} [Deactivated Web User]"
        elif user_obj.is_active:
            is_active = True
            name = f"{report_username} [Active Mobile Worker in '{user['domain']}']"
        else:
            name = f"{report_username} [Deactivated Mobile Worker in '{user['domain']}']"
        return uid, name, is_active


class EnterpriseUserFilter(ExpandedMobileWorkerFilter):
    """User filter for use with enterprise reports. The filter will
    give access to all users across the enterprise provided the current
    domain is the 'source' domain the current user is has no location restrictions
    """

    options_url = "enterprise_user_options"

    def get_default_selections(self):
        return [
            self.utils.user_type_tuple(HQUserType.ACTIVE),
            self.utils.user_type_tuple(HQUserType.DEACTIVATED),
            self.utils.user_type_tuple(HQUserType.WEB),
            self.utils.user_type_tuple(HQUserType.DEACTIVATED_WEB),
        ]

    @property
    @memoized
    def utils(self):
        return EnterpriseUsersUtils(self.domain)

    @property
    def filter_context(self):
        context = super().filter_context
        # this filter doesn't support locations
        context.pop('search_help_inline', None)
        return context

    @classmethod
    def _es_query_domains(cls, domain, request_user):
        if not request_user.has_permission(domain, 'access_all_locations'):
            return super()._es_query_domains(domain, request_user)
        return list(set(EnterprisePermissions.get_domains(domain)) | {domain})


class AffectedUserFilter(EnterpriseUserFilter):
    label = _("Affected User(s)")


class ChangedByUserFilter(EnterpriseUserFilter):
    slug = "changed_by_user"
    label = gettext_lazy("Modified by User(s)")

    def get_default_selections(self):
        return [self.utils.user_type_tuple(HQUserType.WEB),
        self.utils.user_type_tuple(HQUserType.DEACTIVATED_WEB)]


class UserPropertyFilter(BaseSingleOptionFilter):
    label = gettext_noop('Modified Property')
    default_text = gettext_noop('Select Property')
    slug = 'user_property'

    @property
    def options(self):
        from corehq.apps.reports.standard.users.reports import (
            UserHistoryReport,
        )
        properties = UserHistoryReport.get_primary_properties(self.domain)
        properties.pop("username", None)
        return list(properties.items())


class ChangeActionFilter(BaseMultipleOptionFilter):
    ALL = '0'

    label = gettext_noop('Action')
    default_text = gettext_noop('Select Action')
    slug = 'action'

    options = [
        (ALL, gettext_noop('All')),
        (str(UserHistory.CREATE), gettext_noop('Create')),
        (str(UserHistory.UPDATE), gettext_noop('Update')),
    ]
    default_options = ['0']


class UserUploadRecordFilter(BaseSingleOptionFilter):
    label = gettext_noop('User Bulk Upload')
    default_text = gettext_noop('Select upload')
    slug = 'user_upload_record'

    @property
    def options(self):
        timezone = get_timezone_for_user(self.request.couch_user, self.domain)
        records = UserUploadRecord.objects.filter(domain=self.domain).order_by('-date_created')
        return [
            (
                str(record.id),
                _("Upload by {username} at {time}").format(
                    username=cached_user_id_to_user_display(record.user_id),
                    time=ServerTime(record.date_created).user_time(timezone).ui_string(USER_DATETIME_FORMAT)
                )
            )
            for record in records
        ]


class WebUserFilter(BaseMultipleOptionFilter):
    slug = 'web_user'
    label = _('Web user')
    default_text = _('Show all')

    @property
    def options(self):
        query = user_es.UserES().domain(self.domain).web_users()
        return [
            user_details for user_details in query.values_list('username', 'username')
        ]


def get_user_toggle(request):
    ufilter = group = individual = show_commtrack = None
    try:
        if DatatablesServerSideParams.get_value_from_request(request, 'ufilter', ''):
            ufilter = DatatablesServerSideParams.get_value_from_request(
                request, 'ufilter', as_list=True
            )
        group = DatatablesServerSideParams.get_value_from_request(request, 'group', '')
        individual = DatatablesServerSideParams.get_value_from_request(request, 'individual', '')
        show_commtrack = request.project.commtrack_enabled
    except (KeyError, AttributeError):
        pass
    show_filter = True

    toggle = HQUserType.commtrack_defaults() if show_commtrack else HQUserType.use_defaults()
    if ufilter and not (group or individual):
        toggle = HQUserType.use_filter(ufilter)
    elif group or individual:
        show_filter = False
    return toggle, show_filter
