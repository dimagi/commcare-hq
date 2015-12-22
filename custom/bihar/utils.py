from operator import attrgetter
from django.utils.translation import ugettext_noop
from corehq.apps.groups.models import Group
from dimagi.utils.couch.cache import cache_core

ASHA_ROLE = ugettext_noop('ASHA')
AWW_ROLE = ugettext_noop('AWW')
ANM_ROLE = ugettext_noop('ANM')
LS_ROLE = ugettext_noop('LS')

FLW_ROLES = (ASHA_ROLE, AWW_ROLE)
SUPERVISOR_ROLES = (ANM_ROLE, LS_ROLE)


def get_role(user):
    return (user.user_data.get('role') or '').upper()

def get_team_members(group, roles=FLW_ROLES):
    """
    Get any commcare users that are either "asha" or "aww".
    """
    users = group.get_users(only_commcare=True)
    return sorted([u for u in users if get_role(u) in roles],
                  key=lambda u: u.user_data['role'].upper())

def groups_for_user(user, domain):
    if user.is_commcare_user():
        return Group.by_user(user)
    else:
        # for web users just show everything?
        return Group.by_domain(domain)

def get_all_owner_ids(user_ids):
    all_group_ids = [
        row['id']
        for row in Group.get_db().view(
            'groups/by_user',
            keys=user_ids,
            include_docs=False
        )
    ]
    return set(user_ids).union(set(all_group_ids))


def get_all_owner_ids_from_group(group):
    return get_all_owner_ids([user.get_id for user in get_team_members(group)])
