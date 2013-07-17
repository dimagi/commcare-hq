from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
import pytz
from corehq.apps.groups.models import Group
from corehq.apps.reports import util

from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter, BaseReportFilter, BaseSingleOptionFilter, BaseSingleOptionTypeaheadFilter, BaseMultipleOptionTypeaheadFilter
from corehq.apps.groups.hierarchy import (get_hierarchy,
        get_user_data_from_hierarchy)
from corehq.apps.reports.filters.select import MultiSelectGroupTypeaheadFilter
from corehq.apps.reports.models import HQUserType


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

    # todo: Yedi, this looks like a hack on top of another hack. Can we just reexamine this filter?
    always_show_filter = False
    can_be_empty = False


    @property
    def filter_context(self):
        toggle, show_filter = self.get_user_filter(self.request)
        return {
            'show_user_filter': show_filter,
            'toggle_users': toggle,
            'can_be_empty': self.can_be_empty,  # from a merge conflict todo yedi fix
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
        except AttributeError:  # todo, yedi, where does this come in?
            pass

        show_filter = True
        toggle = HQUserType.use_defaults()

        if not cls.always_show_filter and (group or individual):
            show_filter = False
        elif ufilter:
            toggle = HQUserType.use_filter(ufilter)
        return toggle, show_filter


class StrongUserTypeFilter(UserTypeFilter):
    # todo: yedi, fix this. it looks like a hack. we can discuss later. --Biyeun
    """
        Version of the FilterUsersField that always actually uses and shows this filter
        When using this field:
            use SelectMobileWorkerFieldHack instead of SelectMobileWorkerField
            if using ProjectReportParametersMixin make sure filter_users_field_class is set to this
    """
    always_show_filter = True
    can_be_empty = True


class MobileWorkerFilterMixin(object):
    slug = 'individual'
    label = ugettext_noop("Select Mobile Worker")
    default_text = ugettext_noop("All Mobile Workers")

    @classmethod
    def get_default_text(cls, user_filter):
        default = cls.default_text
        if user_filter[HQUserType.ADMIN].show or \
           user_filter[HQUserType.DEMO_USER].show or user_filter[HQUserType.UNKNOWN].show:
            default = _('%s & Others') % _(default)
        return default


class SelectMobileWorkerFilter(MobileWorkerFilterMixin, BaseSingleOptionTypeaheadFilter):

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


class MutiSelectMobileWorkerTypeaheadFilter(MobileWorkerFilterMixin, BaseMultipleOptionTypeaheadFilter):
    default_option = ['_all']
    help_text = ugettext_noop("Click to select mobile workers")
    filter_users_field_class = UserTypeFilter

    @property
    def options(self):
        user_filter, _ = self.filter_users_field_class.get_user_filter(self.request)
        default_text = self.get_default_text(user_filter)
        users = util.user_list(self.domain)
        opts = [(u.get_id, u.raw_username + (' "%s"' % u.full_name if u.full_name else '')) for u in users]
        opts.insert(0, ('_all', default_text))
        return opts


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


class CombinedSelectUsersFilter(BaseReportFilter):
    """
        todo: better docs.
        todo: see what mwhite has done to group filters.
    """
    # todo: yedi, wat? please fix. kthnx. we can discuss. <3 Biyeun
    slug = "combined_select_users"
    label = "Combined Select Users" # todo: use this in your template
    template = "reports/filters/combined_select_users.html"
    filter_users_field_class = StrongUserTypeFilter
    select_mobile_worker_field_class = MutiSelectMobileWorkerTypeaheadFilter
    select_group_field_class = MultiSelectGroupTypeaheadFilter
    show_mobile_worker_field = True
    show_group_field = True

    def __init__(self, request, domain=None, timezone=pytz.utc, parent_report=None):
        super(CombinedSelectUsersFilter, self).__init__(request, domain, timezone, parent_report)

        self.filter_users_field = self.filter_users_field_class(request, domain, timezone, parent_report)
        
        self.select_mobile_worker_field = self.select_mobile_worker_field_class(request, domain, timezone, parent_report)
        self.select_mobile_worker_field.filter_users_field_class = self.filter_users_field_class

        self.select_group_field = self.select_group_field_class(request, domain, timezone, parent_report)

    @property
    def filter_context(self):
        ctxt = {"fuf": self.filter_users_field.filter_context}  # todo: these abbreviations are going to make things horrible to understand in the future. yedi, pls fix
        ctxt['fuf'].update({'field': self.filter_users_field})

        all_groups = self.request.GET.get('all_groups', 'off') == 'on'
        all_mws = self.request.GET.get('all_mws', 'off') == 'on'

        if self.show_mobile_worker_field:
            ctxt["smwf"] = self.select_mobile_worker_field.filter_context
            ctxt['smwf'].update({'field': self.select_mobile_worker_field})

            if all_mws:
                ctxt["smwf"]["select"]["selected"] = []
            else: # remove the _all selection
                ctxt["smwf"]["select"]["selected"] = filter(lambda s: s != '_all', ctxt["smwf"]["select"]["selected"])
            ctxt["smwf"]["select"]["options"] = ctxt["smwf"]["select"]["options"][1:]


        if self.show_group_field:
            ctxt["sgf"] = self.select_group_field.filter_context
            ctxt['sgf'].update({'field': self.select_group_field})

            if all_groups:
                ctxt["sgf"]["select"]["selected"] = []
            else: # remove the _all selection
                ctxt["sgf"]["select"]["selected"] = filter(lambda s: s != '_all', ctxt["sgf"]["select"]["selected"])
            ctxt["sgf"]["select"]["options"] = ctxt["sgf"]["select"]["options"][1:]


        if self.show_mobile_worker_field:
            ctxt["smwf"]["checked"] = all_mws or (not ctxt["smwf"]["select"]["selected"] and not (
                self.show_group_field and (ctxt["sgf"]["select"]["selected"] or all_groups)))

        if self.show_group_field:
            ctxt["sgf"]["checked"] = all_groups or (not ctxt["sgf"]["select"]["selected"] and not (
                self.show_mobile_worker_field and (ctxt["smwf"]["select"]["selected"] or all_mws)))

        return ctxt
