from couchdbkit.exceptions import ResourceNotFound
from django.core.urlresolvers import reverse
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop

from corehq.apps.groups.models import Group
from corehq.apps.users.forms import MultipleSelectionForm
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.views import BaseUserSettingsView
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.excel import alphanumeric_sort_key

def _get_sorted_groups(domain):
    return sorted(
        Group.by_domain(domain),
        key=lambda group: alphanumeric_sort_key(group.name)
    )


class BaseGroupsView(BaseUserSettingsView):

    @method_decorator(require_can_edit_commcare_users)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseGroupsView, self).dispatch(request, *args, **kwargs)

    @property
    def all_groups(self):
        return _get_sorted_groups(self.domain)

    @property
    def main_context(self):
        context = super(BaseGroupsView, self).main_context
        context.update({
            'all_groups': self.all_groups,
        })
        return context


class EditGroupsView(BaseGroupsView):
    template_name = "groups/all_groups.html"
    page_title = ugettext_noop("Groups")
    urlname = 'all_groups'

    @property
    def page_context(self):
        return {}


class EditGroupMembersView(BaseGroupsView):
    urlname = 'group_members'
    page_title = ugettext_noop("Edit Group")
    template_name = 'groups/group_members.html'

    @property
    def page_name(self):
        return _('Editing Group "%s"') % self.group.name

    @property
    def group_id(self):
        return self.kwargs.get('group_id')

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.group_id])

    @property
    @memoized
    def group(self):
        try:
            return Group.get(self.group_id)
        except ResourceNotFound:
            raise Http404("Group %s does not exist" % self.group_id)

    @property
    @memoized
    def member_ids(self):
        return set([u._id for u in self.members])

    @property
    @memoized
    def all_users(self):
        return sorted(CommCareUser.by_domain(self.domain), key=lambda user: user.username)

    @property
    @memoized
    def all_user_ids(self):
        return set([u._id for u in self.all_users])

    @property
    @memoized
    def members(self):
        member_ids = set(self.group.get_user_ids())
        return [u for u in self.all_users if u._id in member_ids]

    @property
    def nonmembers(self):
        member_ids = self.member_ids
        return [u for u in self.all_users if u not in member_ids]

    @property
    @memoized
    def user_selection_form(self):
        def _user_display(user):
            return '{username}{full_name}'.format(
                username=user.raw_username,
                full_name=' (%s)'% user.full_name if user.full_name.strip() else ''
            )

        form = MultipleSelectionForm(initial={
            'selected_ids': list(self.member_ids),
        })
        form.fields['selected_ids'].choices = [(u._id, _user_display(u)) for u in self.all_users]
        return form

    @property
    def page_context(self):
        return {
            'group': self.group,
            'user_form': self.user_selection_form
        }


class EditGroupMembership(BaseGroupsView):
    urlname = 'group_membership'
    page_title = ugettext_noop("Membership Info")
    template_name = 'groups/groups.html'

    @property
    def editable_user_id(self):
        return self.kwargs['couch_user_id']

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain, self.editable_user_id])

    @property
    @memoized
    def editable_user(self):
        return CouchUser.get_by_user_id(self.editable_user_id)

    @property
    @memoized
    def my_groups(self):
        return Group.by_user(self.editable_user_id)

    @property
    def other_groups(self):
        for group in self.all_groups:
            if group.get_id not in [g.get_id for g in self.my_groups]:
                yield group

    @property
    def page_context(self):
        return {
            'groups': self.my_groups,
            'other_grups': list(self.other_groups),
            'couch_user': self.editable_user,
        }

    def post(self, request, *args, **kwargs):
        if 'group' in request.POST:
            group = request.POST['group']
            group.add_user(self.editable_user)
            group.save()
        return self.get(request, *args, **kwargs)
