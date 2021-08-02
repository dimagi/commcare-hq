from django.utils.translation import ugettext as _
from collections import defaultdict

from corehq.apps.users.models import (
    DomainMembershipError,
    StaticRole,
    UserRole,
)


def get_editable_role_choices(domain, couch_user, allow_admin_role):
    """
    :param domain: roles for domain
    :param couch_user: user accessing the roles
    :param allow_admin_role: to include admin role, in case user is admin
    """
    roles = UserRole.objects.get_by_domain(domain)
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
