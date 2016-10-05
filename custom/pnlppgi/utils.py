from couchdbkit import ResourceNotFound
from sqlagg.filters import EQ

from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.util import get_INFilter_element_bindparam
from corehq.apps.users.models import CommCareUser


def update_config(config):
    try:
        group = Group.get('daa2641cf722f8397207c9041bfe5cb3')
        users = group.users
    except ResourceNotFound:
        users = []
    config.update({'users': users})
    config.update(dict({get_INFilter_element_bindparam('owner_id', idx): val for idx, val in enumerate(users, 0)}))


def users_locations():
    try:
        group = Group.get('daa2641cf722f8397207c9041bfe5cb3')
        users = group.users
    except ResourceNotFound:
        users = []
    location_ids = []
    for user in users:
        u = CommCareUser.get(user)
        location_ids.append(u.location_id)
    location_ids = set(location_ids)
    return location_ids


def location_filter(request, params=None, filters=None):
    zone_id = request.GET.get('id_zone', '')
    region_id = request.GET.get('id_region', '')
    district_id = request.GET.get('id_district', '')
    site_id = request.GET.get('id_site', '')
    key = None
    value = None
    if zone_id:
        if region_id:
            if district_id:
                if site_id:
                    key = 'site_id'
                    value = site_id
                else:
                    key = 'district_id'
                    value = district_id
            else:
                key = 'region_id'
                value = district_id
        else:
            key = 'zone_id'
            value = zone_id

    if key and value:
        if params:
            params.update({key: value})
        elif filters:
            filters.append(EQ(key, key))
