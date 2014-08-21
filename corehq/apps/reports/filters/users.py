from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.groups.hierarchy import get_user_data_from_hierarchy

from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.reports.util import namedtupledict
from corehq.apps.users.models import CommCareUser
from corehq.elastic import es_query, ES_URLS
from corehq.util import remove_dups
from dimagi.utils.decorators.memoized import memoized

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
    label = ugettext_noop("User Type")
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

    def group_tuple(self, g):
        return ("g__%s" % g['_id'], "%s [group]" % g['name'])

    def user_type_tuple(self, t):
        return (
            "t__%s" % (t),
            "[%s]" % HQUserType.human_readable[t]
        )

    @property
    @memoized
    def basics(self):
        types = ['DEMO_USER', 'ADMIN', 'UNKNOWN']
        if Domain.get_by_name(self.domain).commtrack_enabled:
            types.append('COMMTRACK')
        user_types = [getattr(HQUserType, t) for t in types]
        basics = [("t__0", _("[All mobile workers]"))] + \
            [self.user_type_tuple(t) for t in user_types]

        if (getattr(self, "show_all_filter", False)
            or (getattr(self, "kwargs", None)
                and "all_data" in self.kwargs)):
            basics = [("t__x", "[All Data]")] + basics

        return basics

_UserData = namedtupledict('_UserData', (
    'users',
    'admin_and_demo_users',
    'groups',
    'users_by_group',
    'combined_users',
))


class ExpandedMobileWorkerFilter(EmwfMixin, BaseMultipleOptionFilter):
    slug = "emw"
    label = ugettext_noop("Groups or Users")
    default_options = None
    placeholder = ugettext_noop(
        "Start typing to specify the groups and users to include in the report."
        " You can select multiple users and groups.")
    is_cacheable = False

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
                commtrack_tuple = self.basics[HQUserType.COMMTRACK]

                defaults.append({
                    'id': commtrack_tuple[0],
                    'text': commtrack_tuple[1]
                })

            return defaults

        basics = dict(self.basics)
        selected = []
        user_ids = []
        group_ids = []
        for s_id in selected_ids:
            if s_id in basics:
                selected.append((s_id, basics.get(s_id)))
            else:
                try:
                    kind, key = s_id.split('__')
                except ValueError:
                    # badly formatted
                    continue
                if kind == 'u':
                    user_ids.append(key)
                elif kind == 'g':
                    group_ids.append(key)

        if group_ids:
            q = {"query": {"filtered": {"filter": {
                "ids": {"values": group_ids}
            }}}}
            res = es_query(
                es_url=ES_URLS["groups"],
                q=q,
                fields=['_id', 'name'],
            )
            selected += [self.group_tuple(hit['fields']) for hit in res['hits']['hits']]
        if user_ids:
            q = {"query": {"filtered": {"filter": {
                "ids": {"values": user_ids}
            }}}}
            res = es_query(
                es_url=ES_URLS["users"],
                q=q,
                fields = ['_id', 'username', 'first_name', 'last_name', 'doc_type'],
            )
            selected += [self.user_tuple(hit['fields']) for hit in res['hits']['hits']]

        known_ids = dict(selected)
        return [{'id': id, 'text': known_ids[id]}
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
    def user_types(cls, request):
        emws = request.GET.getlist(cls.slug)
        return [int(u[3:]) for u in emws
            if (u.startswith("t__") and u[3:].isdigit())]

    @classmethod
    def pull_groups(cls, domain, request):
        emws = request.GET.getlist(cls.slug)
        group_ids = [g[3:] for g in filter(lambda s: s.startswith("g__"), emws)]
        if not group_ids:
            return Group.get_reporting_groups(domain)
        return [Group.get(g) for g in group_ids]

    @classmethod
    def pull_users_from_es(cls, domain, request, initial_query=None, **kwargs):
        emws = request.GET.getlist(cls.slug)
        user_ids = [u[3:] for u in filter(lambda s: s.startswith("u__"), emws)]
        group_ids = [g[3:] for g in filter(lambda s: s.startswith("g__"), emws)]

        if initial_query is None:
            initial_query = {"match_all": {}}
        q = {"query": initial_query}
        doc_types_to_include = ["CommCareUser"]
        if "t__2" in emws:  # Admin users selected
            doc_types_to_include.append("AdminUser")
        if "t__3" in emws:  # Unknown users selected
            doc_types_to_include.append("UnknownUser")

        query_filter = {"and": [
            {"terms": {"doc_type": doc_types_to_include}},
            {"term": {"domain": domain}},
            {"term": {"is_active": True}},
            {"term": {"base_doc": "couchuser"}},
        ]}
        if "t__0" not in emws:
            or_filter = {"or": [
                {"terms": {"_id": user_ids}},
                {"terms": {"__group_ids": group_ids}},
            ]}

            # for setting up an 'or' filter for non commcare users. This occurs when all mobile workers is not selected,
            # but admin, demo, or unknown users are
            other_doc_types = doc_types_to_include[:]
            other_doc_types.remove("CommCareUser")
            if doc_types_to_include:
                or_filter["or"].append({"terms": {"doc_type": other_doc_types}})

            query_filter["and"].append(or_filter)

        if "t__1" in emws:  # Demo user selected
            query_filter = {"or": [{"term": {"username": "demo_user"}}, query_filter]}

        q["filter"] = query_filter
        return es_query(es_url=ES_URLS["users"], q=q, **kwargs)

    @classmethod
    @memoized
    def pull_users_and_groups(cls, domain, request, simplified_users=False, combined=False, CommCareUser=CommCareUser):
        emws = request.GET.getlist(cls.slug)

        users = []
        user_ids = [u[3:] for u in filter(lambda s: s.startswith("u__"), emws)]
        if user_ids or "t__0" in emws:
            users = util.get_all_users_by_domain(domain=domain, user_ids=user_ids, simplified=simplified_users,
                                                 CommCareUser=CommCareUser)

        user_type_ids = [int(t[3:]) for t in filter(lambda s: s.startswith("t__"), emws)]
        user_filter = tuple([HQUserToggle(id, id in user_type_ids) for id in range(4)])
        other_users = util.get_all_users_by_domain(domain=domain, user_filter=user_filter, simplified=simplified_users,
                                                   CommCareUser=CommCareUser)

        group_ids = [g[3:] for g in filter(lambda s: s.startswith("g__"), emws)]
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
    def for_group(cls, group_id):
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
        return 't__x' in emws


def get_user_toggle(request):
    ufilter = group = individual = show_commtrack = None
    try:
        if request.GET.get('ufilter', ''):
            ufilter = request.GET.getlist('ufilter')
        group = request.GET.get('group', '')
        individual = request.GET.get('individual', '')
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
