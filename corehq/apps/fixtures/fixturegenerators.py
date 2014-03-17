from collections import defaultdict
from xml.etree import ElementTree
from django.conf import settings
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.users.models import CommCareUser
from dimagi.utils.modules import to_function


def hq_fixtures(user, version, last_sync):
    if hasattr(user, "_hq_user") and user._hq_user is not None:
        user = user._hq_user
    if isinstance(user, CommCareUser):
        for func_path in settings.HQ_FIXTURE_GENERATORS:
            func = to_function(func_path)
            if func:
                for fixture in func(user, version, last_sync):
                    yield fixture


def item_lists(user, version, last_sync):
    assert isinstance(user, CommCareUser)

    all_types = dict([(t._id, t) for t in FixtureDataType.by_domain(user.domain)])
    global_types = dict([(id, t) for id, t in all_types.items() if t.is_global])

    items_by_type = defaultdict(list)

    def _set_cached_type(item, data_type):
        # set the cached version used by the object so that it doesn't
        # have to do another db trip later
        item._data_type = data_type

    for global_fixture in global_types.values():
        items = list(FixtureDataItem.by_data_type(user.domain, global_fixture))
        _ = [_set_cached_type(item, global_fixture) for item in items]
        items_by_type[global_fixture._id] = items

    other_items = FixtureDataItem.by_user(user)
    data_types = {}

    for item in other_items:
        if item.data_type_id in global_types:
            continue  # was part of the global type so no need to add here
        if not data_types.has_key(item.data_type_id):
            try:
                data_types[item.data_type_id] = all_types[item.data_type_id]
            except (AttributeError, KeyError):
                continue
        items_by_type[item.data_type_id].append(item)
        _set_cached_type(item, data_types[item.data_type_id])

    fixtures = []
    all_types = data_types.values() + global_types.values()
    for data_type in all_types:
        xFixture = ElementTree.Element('fixture', attrib={'id': 'item-list:%s' % data_type.tag, 'user_id': user.user_id})
        xItemList = ElementTree.Element('%s_list' % data_type.tag)
        xFixture.append(xItemList)
        for item in sorted(items_by_type[data_type.get_id], key=lambda x: x.sort_key):
            xItemList.append(item.to_xml())
        fixtures.append(xFixture)
    return fixtures
