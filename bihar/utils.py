from django.utils.translation import ugettext_noop
from corehq.apps.groups.models import Group

ASHA_ROLE = ugettext_noop('ASHA')
AWW_ROLE = ugettext_noop('AWW')


def get_team_members(group):
        """
        Get any commcare users that are either "asha" or "aww".
        """
        users = group.get_users(only_commcare=True)

        def is_team_member(user):
            role = user.user_data.get('role', '')
            return role == ASHA_ROLE or role == AWW_ROLE

        return sorted([u for u in users if is_team_member(u)],
                      key=lambda u: u.user_data['role'])


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