from corehq.apps.reports.standard import CommCareUserMemoizer
from dimagi.utils.web import json_response
from django.shortcuts import render
from corehq.apps.groups.models import Group
from corehq.apps.indicator_fixtures.models import MobileIndicatorSet, MobileIndicatorOwner
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions, CommCareUser


require_can_edit_mobile_indicators = require_permission(Permissions.edit_data)


def strip_json(obj, disallow_basic=None, disallow=None):
    disallow = disallow or []
    if disallow_basic is None:
        disallow_basic = ['_rev', 'domain', 'doc_type']
    disallow += disallow_basic
    ret = {}
    try:
        obj = obj.to_json()
    except Exception:
        pass
    for key in obj:
        if key not in disallow:
            ret[key] = obj[key]

    return ret


def prepare_user(user):
    user.username = user.raw_username
    return strip_json(user, disallow=['password'])


def view(request, domain, template='indicator_fixtures/view.html'):
    indicator_sets = MobileIndicatorSet.by_domain(domain)
    for set in indicator_sets:
        set.users = get_ownerships(domain, set.get_id, 'user')
        set.groups = get_ownerships(domain, set.get_id, 'group')
    return render(request, template, {
        'indicator_sets': indicator_sets,
    })


def get_ownerships(domain, indicator_set_id, type):
    ownerships = MobileIndicatorOwner.by_indicator_set_owner_type(domain, indicator_set_id, type)
    return [CommCareUserMemoizer.get_by_user_id(o.owner_id) for o in ownerships]


@require_can_edit_mobile_indicators
def groups(request, domain):
    groups = Group.by_domain(domain)
    return json_response(map(strip_json, groups))


@require_can_edit_mobile_indicators
def users(request, domain):
    users = CommCareUser.by_domain(domain)
    return json_response(map(prepare_user, users))
