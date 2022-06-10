from django.utils.translation import gettext as _
from collections import defaultdict

from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.models import (
    DomainMembershipError,
    StaticRole,
    UserRole,
)
from corehq.apps.users.util import log_user_change
from corehq.const import USER_CHANGE_VIA_WEB


def get_editable_role_choices(domain, couch_user, allow_admin_role):
    """
    :param domain: roles for domain
    :param couch_user: user accessing the roles
    :param allow_admin_role: to include admin role, in case user is admin
    """
    roles = [role for role in UserRole.objects.get_by_domain(domain)
             if not role.is_commcare_user_default]
    if not couch_user.is_domain_admin(domain):
        try:
            user_role = couch_user.get_role(domain)
        except DomainMembershipError:
            user_role = None
        user_role_id = user_role.get_id if user_role else None
        roles = [
            role for role in roles
            if role.accessible_by_non_admin_role(user_role_id)
        ]
    elif allow_admin_role:
        roles = [StaticRole.domain_admin(domain)] + roles
    return sorted([
        (role.get_qualified_id(), role.name or _('(No Name)'))
        for role in roles
    ], key=lambda c: c[1].lower())


class BulkUploadResponseWrapper(object):

    def __init__(self, context):
        results = context.get('result') or defaultdict(lambda: [])
        self.response_rows = results['rows']
        self.response_errors = results['errors']
        if context['user_type'] == 'web users':
            self.problem_rows = [r for r in self.response_rows if r['flag'] not in ('updated', 'invited')]
        else:
            self.problem_rows = [r for r in self.response_rows if r['flag'] not in ('updated', 'created')]

    def success_count(self):
        return len(self.response_rows) - len(self.problem_rows)

    def has_errors(self):
        return bool(self.response_errors or self.problem_rows)

    def errors(self):
        errors = []
        for row in self.problem_rows:
            if row['flag'] == 'missing-data':
                errors.append(_('A row with no username was skipped'))
            else:
                errors.append('{username}: {flag}'.format(**row))
        errors.extend(self.response_errors)
        return errors


def log_user_groups_change(domain, request, user, group_ids=None):
    groups = []
    # no groups assigned would be group ids as []
    # so if group ids were NOT passed or if some were passed, get groups for user
    if group_ids is None or group_ids:
        groups = Group.by_user_id(user.get_id)
    log_user_change(
        by_domain=domain,
        for_domain=domain,  # Groups are bound to a domain, so use domain
        couch_user=user,
        changed_by_user=request.couch_user,
        changed_via=USER_CHANGE_VIA_WEB,
        change_messages=UserChangeMessage.groups_info(groups)
    )


def log_commcare_user_locations_changes(request, user, old_location_id, old_assigned_location_ids):
    change_messages = {}
    fields_changed = {}
    if old_location_id != user.location_id:
        location = None
        fields_changed['location_id'] = user.location_id
        if user.location_id:
            location = SQLLocation.objects.get(location_id=user.location_id)
        change_messages.update(UserChangeMessage.primary_location_info(location))
    if old_assigned_location_ids != user.assigned_location_ids:
        locations = []
        fields_changed['assigned_location_ids'] = user.assigned_location_ids
        if user.assigned_location_ids:
            locations = SQLLocation.objects.filter(location_id__in=user.assigned_location_ids)
        change_messages.update(UserChangeMessage.assigned_locations_info(locations))

    if change_messages:
        log_user_change(
            by_domain=request.domain,
            for_domain=user.domain,
            couch_user=user,
            changed_by_user=request.couch_user,
            changed_via=USER_CHANGE_VIA_WEB,
            fields_changed=fields_changed,
            change_messages=change_messages
        )
