from operator import attrgetter
from django.utils.translation import ugettext_noop
from corehq.apps.groups.models import Group
from redis_cache.cache import RedisCache
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


def get_calculation(owner_ids, slug):
    from custom.bihar.models import CareBiharFluff
    r = CareBiharFluff.aggregate_results(slug, (
        ['care-bihar', owner_id] for owner_id in owner_ids
    ), reduce=True)
    num = r.get('numerator')
    total = r.get('total')
    r = CareBiharFluff.aggregate_results(slug, (
        ['care-bihar', owner_id] for owner_id in owner_ids
    ), reduce=False)
    num_cases = ', '.join(r.get('numerator', ()))
    total_cases = ', '.join(r.get('total', ()))
    return num or '', total, num_cases, total_cases


def get_all_calculations(owner_ids):

    from custom.bihar.reports.indicators.indicators import IndicatorConfig, INDICATOR_SETS

    config = IndicatorConfig(INDICATOR_SETS)
    for indicator_set in config.indicator_sets:
        for indicator in indicator_set.get_indicators():
            slug = indicator.slug
            yield (indicator.name,) + get_calculation(owner_ids, slug)


def get_groups_for_group(group):
    """This is a helper function only called locally"""
    owner_ids = list(get_all_owner_ids_from_group(group))
    db = Group.get_db()
    rows = db.view('_all_docs', keys=owner_ids, include_docs=True)
    groups = []
    for row in rows:
        doc = row['doc']
        if doc['doc_type'] == 'Group':
            groups.append(Group.wrap(doc))

    groups.sort(key=attrgetter('name'))
    return groups
