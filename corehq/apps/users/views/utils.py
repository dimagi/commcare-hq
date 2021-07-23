from django.utils.translation import ugettext as _
from collections import defaultdict

from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import (
    DomainMembershipError,
    StaticRole,
    SQLUserRole,
)
from corehq.apps.users.util import log_user_change
from corehq.const import USER_CHANGE_VIA_WEB


def get_editable_role_choices(domain, couch_user, allow_admin_role):
    """
    :param domain: roles for domain
    :param couch_user: user accessing the roles
    :param allow_admin_role: to include admin role, in case user is admin
    """
    roles = SQLUserRole.objects.get_by_domain(domain)
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
    return [
        (role.get_qualified_id(), role.name or _('(No Name)'))
        for role in roles
    ]


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
    if group_ids is None:
        group_ids = user.get_group_ids()
    groups_info = None
    if group_ids:
        groups_info = ", ".join(
            f"{group.name}[{group.get_id}]"
            for group in Group.by_user_id(user.get_id)
        )
    log_user_change(
        domain,
        couch_user=user,
        changed_by_user=request.couch_user,
        changed_via=USER_CHANGE_VIA_WEB,
        message=f"Groups: {groups_info}"
    )


def log_commcare_user_locations_changes(domain, request, user, old_location_id, old_assigned_location_ids):
    messages = []
    fields_changed = {}
    if old_location_id != user.location_id:
        location_name = None
        fields_changed['location_id'] = user.location_id
        if user.location_id:
            location_name = SQLLocation.objects.get(location_id=user.location_id).name
        messages.append(f"Primary location: {location_name}")
    if old_assigned_location_ids != user.assigned_location_ids:
        location_names = []
        fields_changed['assigned_location_ids'] = user.assigned_location_ids
        if user.assigned_location_ids:
            location_names = [loc.name
                              for loc in SQLLocation.objects.filter(location_id__in=user.assigned_location_ids)]
        messages.append(f"Assigned locations: {location_names}")

    if messages:
        log_user_change(
            domain,
            couch_user=user,
            changed_by_user=request.couch_user,
            changed_via=USER_CHANGE_VIA_WEB,
            fields_changed=fields_changed,
            message=", ".join(messages)
        )
