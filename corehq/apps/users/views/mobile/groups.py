from couchdbkit.exceptions import ResourceNotFound
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.style.decorators import (
    use_multiselect,
)
from django_prbac.utils import has_privilege
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.views import BaseDomainView
from corehq.apps.domain.models import Domain
from corehq.apps.es.users import UserES
from corehq.apps.groups.models import Group
from corehq.apps.locations.analytics import users_have_locations
from corehq.apps.sms.models import Keyword
from corehq.apps.reminders.models import CaseReminderHandler
from corehq.apps.reports.util import get_simplified_users
from corehq.apps.sms.verify import (
    initiate_sms_verification_workflow,
    VERIFICATION__ALREADY_IN_USE,
    VERIFICATION__ALREADY_VERIFIED,
    VERIFICATION__RESENT_PENDING,
    VERIFICATION__WORKFLOW_STARTED,
)
from corehq.apps.users.forms import MultipleSelectionForm
from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.views import BaseUserSettingsView
from corehq import privileges
from corehq.util.workbook_json.excel import alphanumeric_sort_key
from dimagi.utils.decorators.memoized import memoized


class GroupNotFoundException(Exception):
    pass


def _get_sorted_groups(domain):
    return sorted(
        Group.by_domain(domain),
        key=lambda group: alphanumeric_sort_key(group.name or '')
    )


def get_group_or_404(domain, group_id):
    try:
        group = Group.get(group_id)
        if not group.doc_type.startswith('Group') or group.domain != domain:
            raise GroupNotFoundException()
        return group
    except (ResourceNotFound, GroupNotFoundException):
        raise Http404("Group %s does not exist" % group_id)


class BulkSMSVerificationView(BaseDomainView):
    urlname = 'bulk_sms_verification'

    @method_decorator(require_can_edit_commcare_users)
    @method_decorator(requires_privilege_with_fallback(privileges.INBOUND_SMS))
    def dispatch(self, *args, **kwargs):
        return super(BulkSMSVerificationView, self).dispatch(*args, **kwargs)

    def initiate_verification(self, request, group):
        counts = {
            'users': 0,
            'phone_numbers': 0,
            'phone_numbers_in_use': 0,
            'phone_numbers_already_verified': 0,
            'phone_numbers_pending_verification': 0,
            'workflows_started': 0,
        }
        users_with_error = []

        for user in group.get_users(is_active=True, only_commcare=True):
            counts['users'] += 1
            for phone_number in user.phone_numbers:
                counts['phone_numbers'] += 1
                try:
                    result = initiate_sms_verification_workflow(user, phone_number)
                except Exception:
                    result = None

                if result is None:
                    users_with_error.append(user.raw_username)
                elif result == VERIFICATION__ALREADY_IN_USE:
                    counts['phone_numbers_in_use'] += 1
                elif result == VERIFICATION__ALREADY_VERIFIED:
                    counts['phone_numbers_already_verified'] += 1
                elif result == VERIFICATION__RESENT_PENDING:
                    counts['phone_numbers_pending_verification'] += 1
                elif result == VERIFICATION__WORKFLOW_STARTED:
                    counts['workflows_started'] += 1

        success_msg = _(
            '%(users)s user(s) and %(phone_numbers)s phone number(s) processed. '
            '%(phone_numbers_already_verified)s already verified, '
            '%(phone_numbers_in_use)s already in use by other contact(s), '
            '%(phone_numbers_pending_verification)s already pending verification, '
            'and %(workflows_started)s verification workflow(s) started.'
        ) % counts
        messages.success(request, success_msg)
        if users_with_error:
            error_msg = _(
                'Error processing the following user(s): %(users)s. Please try '
                'again and if the problem persists, report an issue.'
            ) % {'users': ', '.join(set(users_with_error))}
            messages.error(request, error_msg)

    def get(self, request, *args, **kwargs):
        raise Http404()

    def post(self, request, domain, group_id, *args, **kwargs):
        group = get_group_or_404(domain, group_id)
        self.initiate_verification(request, group)
        return HttpResponseRedirect(reverse(EditGroupMembersView.urlname, args=[domain, group_id]))


class BaseGroupsView(BaseUserSettingsView):

    @method_decorator(require_can_edit_commcare_users)
    @use_multiselect
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
            'needs_to_downgrade_locations': (
                users_have_locations(self.domain) and
                not has_privilege(self.request, privileges.LOCATIONS)
            ),
        })
        return context


class GroupsListView(BaseGroupsView):
    template_name = "groups/all_groups.html"
    page_title = ugettext_noop("Groups")
    urlname = 'all_groups'


class EditGroupMembersView(BaseGroupsView):
    urlname = 'group_members'
    page_title = ugettext_noop("Edit Group")
    template_name = 'groups/group_members.html'

    @property
    def parent_pages(self):
        return [{
            'title': GroupsListView.page_title,
            'url': reverse(GroupsListView.urlname, args=(self.domain,)),
        }]

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
        return get_group_or_404(self.domain, self.group_id)

    @property
    @memoized
    def member_ids(self):
        return set([u['user_id'] for u in self.members])

    @property
    @memoized
    def all_users(self):
        return get_simplified_users(
            UserES().mobile_users().domain(self.domain)
        )

    @property
    @memoized
    def all_user_ids(self):
        return set([u['user_id'] for u in self.all_users])

    @property
    @memoized
    def members(self):
        member_ids = set(self.group.get_user_ids())
        return [u for u in self.all_users if u['user_id'] in member_ids]

    @property
    @memoized
    def user_selection_form(self):
        form = MultipleSelectionForm(initial={
            'selected_ids': list(self.member_ids),
        })
        form.fields['selected_ids'].choices = [(u['user_id'], u['username_in_report']) for u in self.all_users]
        return form

    @property
    def page_context(self):
        domain_has_reminders_or_keywords = (
            CaseReminderHandler.domain_has_reminders(self.domain) or
            Keyword.domain_has_keywords(self.domain)
        )
        bulk_sms_verification_enabled = (
            domain_has_reminders_or_keywords and
            domain_has_privilege(self.domain, privileges.INBOUND_SMS)
        )
        return {
            'group': self.group,
            'bulk_sms_verification_enabled': bulk_sms_verification_enabled,
            'num_users': len(self.member_ids),
            'user_form': self.user_selection_form,
            'domain_uses_case_sharing': self.domain_uses_case_sharing,
        }

    @property
    def domain_uses_case_sharing(self):
        domain = Domain.get_by_name(Group.get(self.group_id).domain)
        return domain.case_sharing_included()
