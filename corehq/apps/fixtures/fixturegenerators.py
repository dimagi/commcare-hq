from collections import defaultdict
from xml.etree import ElementTree
from casexml.apps.case.xml import V2
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.users.models import CommCareUser
from couchdbkit.exceptions import ResourceNotFound

def item_lists(user, version=V2, last_sync=None):
    if isinstance(user, CommCareUser):
        pass
    elif hasattr(user, "_hq_user") and user._hq_user is not None:
        user = user._hq_user
    else:
        return []

    items = FixtureDataItem.by_user(user)
    data_types = {}
    items_by_type = defaultdict(list)

    for item in items:
        if not data_types.has_key(item.data_type_id):
            try:
                data_types[item.data_type_id] = FixtureDataType.get(item.data_type_id)
            except ResourceNotFound:
                continue
        items_by_type[item.data_type_id].append(item)
        item._data_type = data_types[item.data_type_id]

    fixtures = []
    for data_type in data_types.values():
        xFixture = ElementTree.Element('fixture', attrib={'id': 'item-list:%s' % data_type.tag, 'user_id': user.user_id})
        xItemList = ElementTree.Element('%s_list' % data_type.tag)
        xFixture.append(xItemList)
        for item in items_by_type[data_type.get_id]:
            xItemList.append(item.to_xml())
        fixtures.append(xFixture)
    return fixtures