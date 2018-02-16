from __future__ import absolute_import
from couchdbkit import ResourceNotFound
from sqlagg.filters import EQ

from corehq.apps.groups.models import Group
from corehq.apps.reports.util import get_INFilter_element_bindparam
from corehq.util.quickcache import quickcache


def update_config(config):
    try:
        group = Group.get('daa2641cf722f8397207c9041bfe5cb3')
        users = group.users
    except ResourceNotFound:
        users = []
    config.update({'users': users})
    config.update(dict({get_INFilter_element_bindparam('owner_id', idx): val for idx, val in enumerate(users, 0)}))


@quickcache([], timeout=3600)
def users_locations():
    try:
        group = Group.get('daa2641cf722f8397207c9041bfe5cb3')
    except ResourceNotFound:
        return set()
    location_ids = set()
    for user in group.get_users():
        location_ids.add(user.location_id)
    return location_ids


def location_filter(request, params=None, filters=None, location_filter_selected=False):
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
                value = region_id
        else:
            key = 'zone_id'
            value = zone_id

    if key and value:
        if params:
            params.update({key: value})
        elif filters:
            filters.append(EQ(key, key))
    if location_filter_selected:
        return value


def show_location(s, ul, sel):
    return s.location_id in ul and (len(sel) == 0 or s.location_id in sel)
