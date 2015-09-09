from couchdbkit.exceptions import ResourceNotFound
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.views import BaseDomainView
from corehq import Domain
from corehq.apps.groups.models import Group
from corehq.apps.reports.util import _report_user_dict
from corehq.apps.sms.verify import (
    initiate_sms_verification_workflow,
    VERIFICATION__ALREADY_IN_USE,
    VERIFICATION__ALREADY_VERIFIED,
    VERIFICATION__RESENT_PENDING,
    VERIFICATION__WORKFLOW_STARTED,
)
from corehq.apps.users.forms import MultipleSelectionForm
from corehq.apps.users.models import CouchUser, CommCareUser
from corehq.apps.users.decorators import require_can_edit_commcare_users
from corehq.apps.users.views import BaseUserSettingsView
from corehq import privileges
from corehq import toggles
from corehq.util.spreadsheets.excel import alphanumeric_sort_key
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
        return get_group_or_404(self.domain, self.group_id)

    @property
    @memoized
    def member_ids(self):
        return set([u['user_id'] for u in self.members])

    @property
    @memoized
    def all_users(self):
        return map(_report_user_dict, sorted(
            CommCareUser.es_fakes(self.domain, wrap=False),
            key=lambda user: user['username']
        ))

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
        bulk_sms_verification_enabled = (
            any(toggles.BULK_SMS_VERIFICATION.enabled(item)
                for item in [self.request.couch_user.username, self.domain]) and
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
