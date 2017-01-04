from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop, ugettext_lazy
from django.utils.translation import ugettext as _

from corehq.apps.es import users as user_es, filters
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.reports.util import namedtupledict
from corehq.apps.users.models import CommCareUser
from corehq.apps.es.users import user_ids_at_locations_and_descendants
from corehq.util import remove_dups, flatten_list
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.commtrack.models import SQLLocation

from .. import util
from ..models import HQUserType, HQUserToggle
from ..analytics.esaccessors import get_user_stubs, get_group_stubs
from .base import (
    BaseMultipleOptionFilter,
    BaseReportFilter,
    BaseSingleOptionFilter,
)


class UserOrGroupFilter(BaseSingleOptionFilter):
    slug = "view_by"
    label = ugettext_noop("View by Users or Groups")
    default_text = ugettext_noop("Users")
    options = [('groups', 'Groups')]


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
    label = ugettext_noop("Select Mobile Worker")
    default_text = ugettext_noop("All Mobile Workers")

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


class AltPlaceholderMobileWorkerFilter(SelectMobileWorkerFilter):
    default_text = ugettext_noop('Enter a worker')


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
        name = "%s [user]" % user['username_in_report']
        return (uid, name)

    def reporting_group_tuple(self, g):
        return ("g__%s" % g['_id'], '%s [group]' % g['name'])

    def user_type_tuple(self, t):
        return (
            "t__%s" % (t),
            "[%s]" % HQUserType.human_readable[t]
        )

    def location_tuple(self, location):
        return ("l__%s" % location.location_id,
                '%s [location]' % location.get_path_display())

    @property
    @memoized
    def static_options(self):
        static_options = [("t__0", _("[All mobile workers]"))]

        types = ['DEMO_USER', 'ADMIN', 'UNKNOWN']
        if Domain.get_by_name(self.domain).commtrack_enabled:
            types.append('COMMTRACK')
        for t in types:
            user_type = getattr(HQUserType, t)
            static_options.append(self.user_type_tuple(user_type))

        return static_options


_UserData = namedtupledict('_UserData', (
    'users',
    'admin_and_demo_users',
    'groups',
    'users_by_group',
    'combined_users',
))


class ExpandedMobileWorkerFilter(BaseMultipleOptionFilter):
    """
    To get raw filter results:
        mobile_user_and_group_slugs = request.GET.getlist(ExpandedMobileWorkerFilter.slug)

        user_ids = emwf.selected_user_ids(mobile_user_and_group_slugs)
        user_types = emwf.selected_user_types(mobile_user_and_group_slugs)
        group_ids = emwf.selected_group_ids(mobile_user_and_group_slugs)
    """
    slug = "emw"
    label = ugettext_lazy("Groups or Users")
    default_options = None
    placeholder = ugettext_lazy(
        "Specify groups and users to include in the report")
    is_cacheable = False
    options_url = 'emwf_options'

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

    def get_default_selections(self):
        defaults = [('t__0', _("[All mobile workers]"))]
        if self.request.project.commtrack_enabled:
            defaults.append(self.utils.user_type_tuple(HQUserType.COMMTRACK))
        return defaults

    @property
    @memoized
    def selected(self):
        selected_ids = self.request.GET.getlist(self.slug)
        if not selected_ids:
            return [{'id': url_id, 'text': text}
                    for url_id, text in self.get_default_selections()]

        selected = (self.selected_static_options(selected_ids) +
                    self._selected_user_entries(selected_ids) +
                    self._selected_group_entries(selected_ids) +
                    self._selected_location_entries(selected_ids))
        known_ids = dict(selected)
        return [
            {'id': id, 'text': known_ids[id]}
            for id in selected_ids
            if id in known_ids
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
        return map(self.utils.location_tuple,
                   SQLLocation.objects.filter(location_id__in=location_ids))

    @property
    def filter_context(self):
        context = super(ExpandedMobileWorkerFilter, self).filter_context
        url = reverse(self.options_url, args=[self.domain])
        context.update({'endpoint': url})
        return context

    @classmethod
    def user_es_query(cls, domain, mobile_user_and_group_slugs):
        user_ids = cls.selected_user_ids(mobile_user_and_group_slugs)
        user_types = cls.selected_user_types(mobile_user_and_group_slugs)
        group_ids = cls.selected_group_ids(mobile_user_and_group_slugs)
        location_ids = cls.selected_location_ids(mobile_user_and_group_slugs)

        user_type_filters = []
        if HQUserType.ADMIN in user_types:
            user_type_filters.append(user_es.admin_users())
        if HQUserType.UNKNOWN in user_types:
            user_type_filters.append(user_es.unknown_users())
            user_type_filters.append(user_es.web_users())
        if HQUserType.DEMO_USER in user_types:
            user_type_filters.append(user_es.demo_users())

        q = user_es.UserES().domain(domain)
        if HQUserType.REGISTERED in user_types:
            # return all users with selected user_types
            user_type_filters.append(user_es.mobile_users())
            return q.OR(*user_type_filters)
        else:
            # return matching user types and exact matches
            location_ids = list(SQLLocation.active_objects
                                .get_locations_and_children(location_ids)
                                .location_ids())
            id_filter = filters.OR(
                filters.term("_id", user_ids),
                filters.term("__group_ids", group_ids),
                user_es.location(location_ids),
            )
            if user_type_filters:
                return q.OR(
                    id_filter,
                    filters.OR(*user_type_filters),
                )
            else:
                return q.filter(id_filter)

    @classmethod
    def pull_users_and_groups(cls, domain, mobile_user_and_group_slugs,
                              include_inactive=False, limit_user_ids=None):
        user_ids = set(cls.selected_user_ids(mobile_user_and_group_slugs))
        user_types = cls.selected_user_types(mobile_user_and_group_slugs)
        group_ids = cls.selected_group_ids(mobile_user_and_group_slugs)
        location_ids = cls.selected_location_ids(mobile_user_and_group_slugs)
        users = []

        if location_ids:
            user_ids |= set(user_ids_at_locations_and_descendants(location_ids))

        if limit_user_ids:
            user_ids = set(limit_user_ids).intersection(user_ids)

        if user_ids or HQUserType.REGISTERED in user_types:
            users = util.get_all_users_by_domain(
                domain=domain,
                user_ids=user_ids,
                simplified=True,
                CommCareUser=CommCareUser,
            )
        user_filter = tuple([HQUserToggle(id, id in user_types) for id in range(4)])
        other_users = util.get_all_users_by_domain(
            domain=domain,
            user_filter=user_filter,
            simplified=True,
            CommCareUser=CommCareUser,
            include_inactive=include_inactive
        )
        groups = [Group.get(g) for g in group_ids]
        all_users = users + other_users

        user_dict = {}
        for group in groups:
            users_in_group = util.get_all_users_by_domain(
                group=group,
                simplified=True
            )
            if limit_user_ids:
                users_in_group = filter(lambda user: user['user_id'] in limit_user_ids, users_in_group)
            user_dict["%s|%s" % (group.name, group._id)] = users_in_group

        users_in_groups = flatten_list(user_dict.values())
        users_by_group = user_dict
        combined_users = remove_dups(all_users + users_in_groups, "user_id")

        return _UserData(
            users=all_users,
            admin_and_demo_users=other_users,
            groups=groups,
            users_by_group=users_by_group,
            combined_users=combined_users,
        )

    @property
    def options(self):
        return [('t__0', _("[All mobile workers]"))]

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

    def _get_assigned_locations_default(self):
        user_assigned_locations = self.request.couch_user.get_sql_locations(
            self.request.domain
        )
        return map(self.utils.location_tuple, user_assigned_locations)


class LocationRestrictedMobileWorkerFilter(ExpandedMobileWorkerFilter):
    options_url = 'new_emwf_options'

    def get_default_selections(self):
        if self.request.can_access_all_locations:
            return super(LocationRestrictedMobileWorkerFilter, self).get_default_selections()
        else:
            return self._get_assigned_locations_default()

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
