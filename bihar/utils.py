from operator import attrgetter
from django.utils.translation import ugettext_noop
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser

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


def get_all_calculations(group_id):
    from bihar.models import CareBiharFluff
    from bihar.reports.indicators.indicators import IndicatorConfig, INDICATOR_SETS

    config = IndicatorConfig(INDICATOR_SETS)
    for indicator_set in config.indicator_sets:
        print indicator_set.name
        for indicator in indicator_set.get_indicators():
            slug = indicator.slug
            user_ids = [user.get_id for user in get_team_members(Group.get(group_id))]
            owner_ids = get_all_owner_ids(user_ids)
            r = CareBiharFluff.aggregate_results(slug, (
                ['care-bihar', owner_id] for owner_id in owner_ids
            ))
            num = r.get('numerator')
            total = r.get('total')
            r = CareBiharFluff.aggregate_results(slug, (
                ['care-bihar', owner_id] for owner_id in owner_ids
            ), reduce=False)
            num_cases = ', '.join(r.get('numerator', ()))
            total_cases = ', '.join(r.get('total', ()))
            yield (
                indicator.name,
                num or '',
                total,
                num_cases,
                total_cases
            )


def get_groups_for_group(group_id):
    """This is a helper function only called locally"""
    user_ids = [user.get_id for user in get_team_members(Group.get(group_id))]
    owner_ids = list(get_all_owner_ids(user_ids))
    db = Group.get_db()
    rows = db.view('_all_docs', keys=owner_ids, include_docs=True)
    groups = []
    for row in rows:
        doc = row['doc']
        if doc['doc_type'] == 'Group':
            groups.append(Group.wrap(doc))

    groups.sort(key=attrgetter('name'))
    return groups