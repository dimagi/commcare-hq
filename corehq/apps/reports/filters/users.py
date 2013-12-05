from corehq.apps.users.models import CommCareUser
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from corehq.apps.groups.models import Group
from corehq.apps.reports import util

from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseReportFilter, BaseSingleOptionFilter, BaseSingleOptionTypeaheadFilter, BaseMultipleOptionFilter
from corehq.apps.groups.hierarchy import (get_hierarchy,
        get_user_data_from_hierarchy)
from corehq.apps.reports.models import HQUserType, HQUserToggle


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
        ufilter = group = individual = None
        try:
            if request.GET.get('ufilter', ''):
                ufilter = request.GET.getlist('ufilter')
            group = request.GET.get('group', '')
            individual = request.GET.get('individual', '')
        except KeyError:
            pass
        show_filter = True
        toggle = HQUserType.use_defaults()
        if ufilter and not (group or individual):
            toggle = HQUserType.use_filter(ufilter)
        elif group or individual:
            show_filter = False
        return toggle, show_filter


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

class ExpandedMobileWorkerFilter(BaseMultipleOptionFilter):
    slug = "emw"
    label = ugettext_noop("User/Group Filter")
    default_options = ["_all_mobile_workers"]

    @classmethod
    @memoized
    def pull_users_and_groups(cls, domain, request, simplified_users=False, combined=False, CommCareUser=CommCareUser):
        emws = request.GET.getlist('emw')

        users = []
        user_ids = [u[3:] for u in filter(lambda s: s.startswith("u__"), emws)]
        if user_ids or "_all_mobile_workers" in emws:
            users = util.get_all_users_by_domain(domain=domain, user_ids=user_ids, simplified=simplified_users,
                                                 CommCareUser=CommCareUser)

        user_type_ids = [int(t[3:]) for t in filter(lambda s: s.startswith("t__"), emws)]
        user_filter = tuple([HQUserToggle(id, id in user_type_ids) for id in range(4)])
        other_users = util.get_all_users_by_domain(domain=domain, user_filter=user_filter, simplified=simplified_users,
                                                   CommCareUser=CommCareUser)

        group_ids = [g[3:] for g in filter(lambda s: s.startswith("g__"), emws)]
        groups = [Group.get(g) for g in group_ids]

        ret = {
            "users": users + other_users,
            "admin_and_demo_users": other_users,
            "groups": groups,
        }

        if combined:
            user_dict = {}
            for group in groups:
                user_dict["%s|%s" % (group.name, group._id)] = util.get_all_users_by_domain(
                    group=group,
                    simplified=simplified_users
                )

            users_in_groups = [user for sublist in user_dict.values() for user in sublist]

            ret["users_by_group"] = user_dict
            ret["combined_users"] = ret["users"] + users_in_groups
        return ret

    @property
    def options(self):
        user_type_opts = [("t__%s" % (i+1), "[%s]" % name) for i, name in enumerate(HQUserType.human_readable[1:])]
        user_opts = [("u__%s" % u.get_id, "%s [user]" % u.human_friendly_name) for u in util.user_list(self.domain)]
        group_opts = [("g__%s" % g.get_id, "%s [group]" % g.name) for g in Group.get_reporting_groups(self.domain)]
        return [("_all_mobile_workers", _("[All mobile workers]"))] + user_type_opts + user_opts + group_opts


