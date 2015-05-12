from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop, ugettext_lazy
from django.utils.translation import ugettext as _

from corehq.apps.es import users as user_es, filters
from corehq.apps.locations.models import LOCATION_SHARING_PREFIX, LOCATION_REPORTING_PREFIX
from corehq.apps.domain.models import Domain
from corehq.apps.groups.hierarchy import get_user_data_from_hierarchy
from corehq.apps.groups.models import Group
from corehq.apps.reports.util import namedtupledict
from corehq.apps.users.models import CommCareUser
from corehq.elastic import es_query, ES_URLS
from corehq.util import remove_dups
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.commtrack.models import SQLLocation

from .. import util
from ..models import HQUserType, HQUserToggle
from .base import (
    BaseDrilldownOptionFilter,
    BaseMultipleOptionFilter,
    BaseReportFilter,
    BaseSingleOptionFilter,
    BaseSingleOptionTypeaheadFilter,
)


class LinkedUserFilter(BaseDrilldownOptionFilter):
    """
    Lets you define hierarchical user groups by adding semantics to the
    following group metadata properties:

    On the root user group containing the top-level users:
        user_type:  name of user type

    On each group defining an association between one level-N user and many
    level-N+1 users:
        owner_name:  username of the owning user
        owner_type:  name of user type for the owner
        child_type:  name of user type for the child

    Then you define the user_types attribute of this class as a list of user
    types.

    """
    slug = "user"
    label = ugettext_noop("Select User(s)")

    # (parent_type, child_type[, child_type...]) as defined in the
    # user-editable group metadata
    user_types = None
    domain = None

    # Whether to use group names for intermediate selectors instead of the
    # username of the group's owner
    use_group_names = False

    @classmethod
    def get_labels(cls):
        for type in cls.user_types:
            yield (
                type,
                _("Select %(child_type)s") % {'child_type': type}, 
                type
            )

    @property
    def drilldown_empty_text(self):
        return _("An error occured while making this linked user "
                 "filter. Make sure you have created a group containing "
                 "all %(root_type)ss with the metadata property 'user_type' set "
                 "to '%(root_type)s' and added owner_type and child_type "
                 "metadata properties to all of the necessary other groups.") % {
            "root_type": self.user_types[0]
        }

    @property
    def drilldown_map(self):
        try:
            hierarchy = get_hierarchy(self.domain, self.user_types)
        except Exception:
            return []

        def get_values(node, level):
            ret = {
                'val': node['user']._id
            }
            if node.get('child_group') and self.use_group_names:
                ret['text'] = node['child_group'].name
            else:
                ret['text'] = node['user'].raw_username

            if 'descendants' in node:
                ret['next'] = [get_values(node, level + 1) 
                               for node in node['descendants']]
            elif node.get('child_users'):
                ret['next'] = [{
                    'val': c._id,
                    'text': c.raw_username
                } for c in node['child_users']]
            else:
                ret['next'] = [{
                    'val': '',
                    'text': _("No %(child_type)ss found for this %(parent_type)s.") % {
                                'parent_type': self.user_types[level],
                                'child_type': self.user_types[level + 1]}
                }]

            return ret

        return [get_values(top_level_node, 0) for top_level_node in hierarchy]

    @classmethod
    def get_user_data(cls, request_params, domain=None):
        domain = domain or cls.domain

        selected_user_id = None

        for user_type in reversed(cls.user_types):
            user_id = request_params.get("%s_%s" % (cls.slug, user_type))
            if user_id:
                selected_user_id = user_id
                break

        return get_user_data_from_hierarchy(domain, cls.user_types,
                root_user_id=selected_user_id)


class UserTypeFilter(BaseReportFilter):
    # note, this is a butchered refactor of the original FilterUsersField.
    # don't use this as a guideline for anything.
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


class SelectMobileWorkerFilter(BaseSingleOptionTypeaheadFilter):
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


class EmwfMixin(object):

    def user_tuple(self, u):
        user = util._report_user_dict(u)
        uid = "u__%s" % user['user_id']
        name = "%s [user]" % user['username_in_report']
        return (uid, name)

    def reporting_group_tuple(self, g):
        return ("g__%s" % g['_id'], '%s [group]' % g['name'])

    def sharing_group_tuple(self, g):
        return ("sg__%s" % g['_id'], '%s [case sharing]' % g['name'])

    def user_type_tuple(self, t):
        return (
            "t__%s" % (t),
            "[%s]" % HQUserType.human_readable[t]
        )

    @property
    @memoized
    def user_types(self):
        types = ['DEMO_USER', 'ADMIN', 'UNKNOWN']
        if Domain.get_by_name(self.domain).commtrack_enabled:
            types.append('COMMTRACK')
        user_types = [getattr(HQUserType, t) for t in types]
        user_type_tuples = [("t__0", _("[All mobile workers]"))] + \
            [self.user_type_tuple(t) for t in user_types]
        if (getattr(self, "show_all_filter", False)
            or (getattr(self, "kwargs", None)
                and "all_data" in self.kwargs)):
            user_type_tuples = [("all_data", "[All Data]")] + user_type_tuples
        return user_type_tuples

    def get_location_groups(self):
        locations = SQLLocation.objects.filter(
            name__icontains=self.q.lower(),
            domain=self.domain,
        )
        for loc in locations:
            group = loc.reporting_group_object()
            yield (group._id, group.name + ' [group]')

        if self.include_share_groups:
            # filter out any non case share type locations for this part
            locations = locations.filter(location_type__shares_cases=True)
            for loc in locations:
                group = loc.case_sharing_group_object()
                yield (group._id, group.name + ' [case sharing]')


_UserData = namedtupledict('_UserData', (
    'users',
    'admin_and_demo_users',
    'groups',
    'users_by_group',
    'combined_users',
))


class ExpandedMobileWorkerFilter(EmwfMixin, BaseMultipleOptionFilter):
    """
    To get raw filter results:

        user_ids = emwf.selected_user_ids(request)
        user_types = emwf.selected_user_types(request)
        group_ids = emwf.selected_group_ids(request)
    """
    slug = "emw"
    label = ugettext_lazy("Groups or Users")
    default_options = None
    placeholder = ugettext_lazy(
        "Start typing to specify the groups and users to include in the report."
        " You can select multiple users and groups.")
    is_cacheable = False

    @classmethod
    def selected_user_ids(cls, request):
        emws = request.GET.getlist(cls.slug)
        return [u[3:] for u in emws if u.startswith("u__")]

    @classmethod
    def selected_user_types(cls, request):
        """
        usage: ``HQUserType.DEMO_USER in selected_user_types``
        """
        emws = request.GET.getlist(cls.slug)
        return [int(t[3:]) for t in emws
                if t.startswith("t__") and t[3:].isdigit()]

    @classmethod
    def selected_group_ids(cls, request):
        return cls.selected_reporting_group_ids(request) +\
               cls.selected_sharing_group_ids(request)

    @classmethod
    def selected_reporting_group_ids(cls, request):
        emws = request.GET.getlist(cls.slug)
        return [g[3:] for g in emws if g.startswith("g__")]

    @classmethod
    def selected_sharing_group_ids(cls, request):
        emws = request.GET.getlist(cls.slug)
        return [g[4:] for g in emws if g.startswith("sg__")]

    @classmethod
    def selected_location_sharing_group_ids(cls, request):
        emws = request.GET.getlist(cls.slug)
        return [
            g for g in emws if g.startswith(LOCATION_SHARING_PREFIX)
        ]

    @classmethod
    def selected_location_reporting_group_ids(cls, request):
        emws = request.GET.getlist(cls.slug)
        return [
            g for g in emws if g.startswith(LOCATION_REPORTING_PREFIX)
        ]

    @property
    @memoized
    def selected(self):
        selected_ids = self.request.GET.getlist(self.slug)
        if not selected_ids:
            defaults = [{
                'id': 't__0',
                'text': _("[All mobile workers]"),
            }]
            if self.request.project.commtrack_enabled:
                commtrack_tuple = self.user_type_tuple(HQUserType.COMMTRACK)
                defaults.append({
                    'id': commtrack_tuple[0],
                    'text': commtrack_tuple[1]
                })
            return defaults

        user_ids = self.selected_user_ids(self.request)
        user_types = self.selected_user_types(self.request)
        group_ids = self.selected_group_ids(self.request)
        location_sharing_ids = self.selected_location_sharing_group_ids(self.request)
        location_reporting_ids = self.selected_location_reporting_group_ids(self.request)

        selected = [t for t in self.user_types
                    if t[0][3:].isdigit() and int(t[0][3:]) in user_types]
        if group_ids:
            q = {"query": {"filtered": {"filter": {
                "ids": {"values": group_ids}
            }}}}
            res = es_query(
                es_url=ES_URLS["groups"],
                q=q,
                fields=['_id', 'name', "case_sharing", "reporting"],
            )
            for group in res['hits']['hits']:
                if group['fields'].get("reporting", False):
                    selected.append(self.reporting_group_tuple(group['fields']))
                if group['fields'].get("case_sharing", False):
                    selected.append(self.sharing_group_tuple(group['fields']))

        if location_sharing_ids:
            from corehq.apps.commtrack.models import SQLLocation
            for loc_group_id in location_sharing_ids:
                loc = SQLLocation.objects.get(
                    location_id=loc_group_id.replace(LOCATION_SHARING_PREFIX, '')
                )
                loc_group = loc.case_sharing_group_object()
                selected.append((loc_group._id, loc_group.name + ' [case sharing]'))

        if location_reporting_ids:
            from corehq.apps.commtrack.models import SQLLocation
            for loc_group_id in location_reporting_ids:
                loc = SQLLocation.objects.get(
                    location_id=loc_group_id.replace(LOCATION_REPORTING_PREFIX, '')
                )
                loc_group = loc.reporting_group_object()
                selected.append((loc_group._id, loc_group.name + ' [group]'))

        if user_ids:
            q = {"query": {"filtered": {"filter": {
                "ids": {"values": user_ids}
            }}}}
            res = es_query(
                es_url=ES_URLS["users"],
                q=q,
                fields=['_id', 'username', 'first_name', 'last_name', 'doc_type'],
            )
            selected += [self.user_tuple(hit['fields']) for hit in res['hits']['hits']]

        known_ids = dict(selected)
        return [
            {'id': id, 'text': known_ids[id]}
            for id in selected_ids
            if id in known_ids
        ]

    @property
    def filter_context(self):
        context = super(ExpandedMobileWorkerFilter, self).filter_context
        url = reverse('emwf_options', args=[self.domain])
        context.update({'endpoint': url})
        return context

    @classmethod
    def pull_groups(cls, domain, request):
        group_ids = cls.selected_group_ids(request)
        if not group_ids:
            return Group.get_reporting_groups(domain)
        return [Group.get(g) for g in group_ids]

    @classmethod
    def user_es_query(cls, domain, request):
        user_ids = cls.selected_user_ids(request)
        user_types = cls.selected_user_types(request)
        group_ids = cls.selected_group_ids(request)

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
            id_filter = filters.OR(
                filters.term("_id", user_ids),
                filters.term("__group_ids", group_ids),
            )
            if user_type_filters:
                return q.OR(
                    id_filter,
                    filters.OR(*user_type_filters),
                )
            else:
                return q.filter(id_filter)


    @classmethod
    @memoized
    def pull_users_and_groups(cls, domain, request, simplified_users=False,
            combined=False, CommCareUser=CommCareUser, include_inactive=False):
        user_ids = cls.selected_user_ids(request)
        user_types = cls.selected_user_types(request)
        group_ids = cls.selected_group_ids(request)
        users = []
        if user_ids or HQUserType.REGISTERED in user_types:
            users = util.get_all_users_by_domain(
                domain=domain,
                user_ids=user_ids,
                simplified=simplified_users,
                CommCareUser=CommCareUser,
            )
        user_filter = tuple([HQUserToggle(id, id in user_types) for id in range(4)])
        other_users = util.get_all_users_by_domain(domain=domain, user_filter=user_filter, simplified=simplified_users,
                                                   CommCareUser=CommCareUser, include_inactive=include_inactive)
        groups = [Group.get(g) for g in group_ids]
        all_users = users + other_users
        if combined:
            user_dict = {}
            for group in groups:
                user_dict["%s|%s" % (group.name, group._id)] = util.get_all_users_by_domain(
                    group=group,
                    simplified=simplified_users
                )
            users_in_groups = [user for sublist in user_dict.values() for user in sublist]
            users_by_group = user_dict
            combined_users = remove_dups(all_users + users_in_groups, "user_id")
        else:
            users_by_group = None
            combined_users = None
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


class ExpandedMobileWorkerFilterWithAllData(ExpandedMobileWorkerFilter):
    show_all_filter = True

    @property
    def filter_context(self):
        context = super(ExpandedMobileWorkerFilterWithAllData, self).filter_context
        url = reverse('emwf_options_with_all_data', args=[self.domain])
        context.update({'endpoint': url})
        return context

    @classmethod
    def show_all_data(cls, request):
        emws = request.GET.getlist(cls.slug)
        return 'all_data' in emws

    @property
    @memoized
    def selected(self):
        selected = super(ExpandedMobileWorkerFilterWithAllData, self).selected
        if self.show_all_data(self.request):
            selected = [{'id': 'all_data', 'text': "[All Data]"}] + selected
        return selected


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
