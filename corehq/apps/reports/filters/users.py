from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop, ugettext_lazy
from django.utils.translation import ugettext as _

from memoized import memoized

from corehq.apps.es import users as user_es, filters
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.permissions import user_can_access_other_user
from corehq.apps.userreports.reports.filters.values import CHOICE_DELIMITER
from corehq.apps.users.cases import get_wrapped_owner
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.commtrack.models import SQLLocation
from corehq.toggles import FILTER_ON_GROUPS_AND_LOCATIONS

from .. import util
from ..models import HQUserType
from ..analytics.esaccessors import get_user_stubs, get_group_stubs
from .base import (
    BaseMultipleOptionFilter,
    BaseReportFilter,
    BaseSingleOptionFilter,
)
from six.moves import map


class UserOrGroupFilter(BaseSingleOptionFilter):
    slug = "view_by"
    label = ugettext_lazy("View by Users or Groups")
    default_text = ugettext_lazy("Users")
    options = [('groups', ugettext_lazy('Groups'))]


class UserTypeFilter(BaseReportFilter):
    # note, don't use this as a guideline for anything.
    slug = "ufilter"
    label = ugettext_lazy("User Type")
    template = "reports/filters/filter_users.html"

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
    label = ugettext_lazy("Select Mobile Worker")
    default_text = ugettext_lazy("All Mobile Workers")

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


class SelectCaseOwnerFilter(SelectMobileWorkerFilter):
    label = ugettext_noop("Select Case Owner")
    default_text = ugettext_noop("All Case Owners")

    @property
    def options(self):
        options = [(group._id, "%s (Group)" % group.name) for group in Group.get_case_sharing_groups(self.domain)]
        user_options = super(SelectCaseOwnerFilter, self).options
        options.extend(user_options)
        return options


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
    def __init__(self, domain):
        self.domain = domain

    def user_tuple(self, u):
        user = util._report_user_dict(u)
        uid = "u__%s" % user['user_id']
        is_active = False
        if u['doc_type'] == 'WebUser':
            name = "%s [Web User]" % user['username_in_report']
        elif user['is_active']:
            is_active = True
            name = "%s [Active Mobile Worker]" % user['username_in_report']
        else:
            name = "%s [Deactivated Mobile Worker]" % user['username_in_report']
        return uid, name, is_active

    def reporting_group_tuple(self, g):
        return "g__%s" % g['_id'], '%s [group]' % g['name']

    def user_type_tuple(self, t):
        return (
            "t__%s" % t,
            "[%s]" % HQUserType.human_readable[t]
        )

    def location_tuple(self, location):
        return ("l__%s" % location.location_id,
                '%s [location]' % location.get_path_display())

    @property
    @memoized
    def static_options(self):
        static_options = [("t__0", _("[Active Mobile Workers]"))]

        types = ['DEACTIVATED', 'DEMO_USER', 'ADMIN', 'WEB', 'UNKNOWN']
        if Domain.get_by_name(self.domain).commtrack_enabled:
            types.append('COMMTRACK')
        for t in types:
            user_type = getattr(HQUserType, t)
            static_options.append(self.user_type_tuple(user_type))

        return static_options

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
            if (callable(owner.is_deleted) and owner.is_deleted()) or owner.is_deleted == True:
                # is_deleted may be an attr or callable depending on owner type
                ret = (ret[0], 'Deleted - ' + ret[1])

        return ret


class UsersUtils(EmwfUtils):

    def user_tuple(self, u):
        user = util._report_user_dict(u)
        uid = "%s" % user['user_id']
        name = "%s" % user['username_in_report']
        return (uid, name)


class ExpandedMobileWorkerFilter(BaseMultipleOptionFilter):
    """
    To get raw filter results:
        mobile_user_and_group_slugs = request.GET.getlist(ExpandedMobileWorkerFilter.slug)

        user_ids = emwf.selected_user_ids(mobile_user_and_group_slugs)
        user_types = emwf.selected_user_types(mobile_user_and_group_slugs)
        group_ids = emwf.selected_group_ids(mobile_user_and_group_slugs)
    """
    slug = "emw"
    label = ugettext_lazy("User(s)")
    default_options = None
    placeholder = ugettext_lazy("Add users and groups to filter this report.")
    is_cacheable = False
    options_url = 'emwf_options_all_users'
    filter_help_inline = ugettext_lazy(mark_safe(
        'See <a href="https://confluence.dimagi.com/display/commcarepublic/Report+and+Export+Filters"'
        ' target="_blank"> Filter Definitions</a>.'
    ))
    search_help_inline = ugettext_lazy(mark_safe(
        'To quick search for a '
        '<a href="https://confluence.dimagi.com/display/commcarepublic/Exact+Search+for+Locations" '
        'target="_blank">location</a>, write your query as "parent"/descendant.'
    ))

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
        return [g[3:] for g in mobile_user_and_group_slugs if g.startswith("g__")]

    @staticmethod
    def selected_location_ids(mobile_user_and_group_slugs):
        return [l[3:] for l in mobile_user_and_group_slugs if l.startswith("l__")]

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

        defaults = [('t__0', _("[Active Mobile Workers]")), ('t__5', _("[Deactivated Mobile Workers]"))]
        if self.request.project.commtrack_enabled:
            defaults.append(self.utils.user_type_tuple(HQUserType.COMMTRACK))
        return defaults

    @property
    @memoized
    def selected(self):
        selected_ids = []
        for ids in self.request.GET.getlist(self.slug):
            selected_ids.extend(ids.split(CHOICE_DELIMITER))
        if not selected_ids:
            return [{'id': url_id, 'text': text}
                    for url_id, text in self.get_default_selections()]

        selected = (self.selected_static_options(selected_ids) +
                    self._selected_user_entries(selected_ids) +
                    self._selected_group_entries(selected_ids) +
                    self._selected_location_entries(selected_ids))
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
            context.update({'search_help_inline': self.search_help_inline})
        return context

    @classmethod
    def user_es_query(cls, domain, mobile_user_and_group_slugs, request_user):
        # The queryset returned by this method is location-safe
        q = user_es.UserES().domain(domain)
        if ExpandedMobileWorkerFilter.no_filters_selected(mobile_user_and_group_slugs):
            return q.show_inactive()

        user_ids = cls.selected_user_ids(mobile_user_and_group_slugs)
        user_types = cls.selected_user_types(mobile_user_and_group_slugs)
        group_ids = cls.selected_group_ids(mobile_user_and_group_slugs)
        location_ids = cls.selected_location_ids(mobile_user_and_group_slugs)

        user_type_filters = []
        if HQUserType.ADMIN in user_types:
            user_type_filters.append(user_es.admin_users())
        if HQUserType.UNKNOWN in user_types:
            user_type_filters.append(user_es.unknown_users())
        if HQUserType.WEB in user_types:
            user_type_filters.append(user_es.web_users())
        if HQUserType.DEMO_USER in user_types:
            user_type_filters.append(user_es.demo_users())

        if HQUserType.ACTIVE in user_types and HQUserType.DEACTIVATED in user_types:
            q = q.show_inactive()
        elif HQUserType.DEACTIVATED in user_types:
            q = q.show_only_inactive()

        if not request_user.has_permission(domain, 'access_all_locations'):
            cls._verify_users_are_accessible(domain, request_user, user_ids)
            return q.OR(
                filters.term("_id", user_ids),
                user_es.location(list(SQLLocation.active_objects
                                      .get_locations_and_children(location_ids)
                                      .accessible_to_user(domain, request_user)
                                      .location_ids())),
            )

        if HQUserType.ACTIVE in user_types or HQUserType.DEACTIVATED in user_types:
            # return all users with selected user_types
            user_type_filters.append(user_es.mobile_users())
            return q.OR(*user_type_filters)

        # return matching user types and exact matches
        location_ids = list(SQLLocation.active_objects
                            .get_locations_and_children(location_ids)
                            .location_ids())

        group_id_filter = filters.term("__group_ids", group_ids)

        if FILTER_ON_GROUPS_AND_LOCATIONS.enabled(domain) and group_ids and location_ids:
            group_and_location_filter = filters.AND(
                group_id_filter,
                user_es.location(location_ids),
            )
        else:
            group_and_location_filter = filters.OR(
                group_id_filter,
                user_es.location(location_ids),
            )

        id_filter = filters.OR(
            filters.term("_id", user_ids),
            group_and_location_filter,
        )

        if user_type_filters:
            return q.OR(
                id_filter,
                group_and_location_filter,
                filters.OR(*user_type_filters),
            )
        return q.filter(id_filter)

    @staticmethod
    def _verify_users_are_accessible(domain, request_user, user_ids):
        # This function would be very slow if called with many user ids
        for user_id in user_ids:
            other_user = CommCareUser.get(user_id)
            if not user_can_access_other_user(domain, request_user, other_user):
                raise PermissionDenied("One or more users are not accessible")

    @property
    def options(self):
        return [('t__0', _("[Active Mobile Workers]"))]

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


def get_user_toggle(request):
    ufilter = group = individual = show_commtrack = None
    try:
        request_obj = request.POST if request.method == 'POST' else request.GET
        if request_obj.get('ufilter', ''):
            ufilter = request_obj.getlist('ufilter')
        group = request_obj.get('group', '')
        individual = request_obj.get('individual', '')
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
