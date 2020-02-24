from collections import defaultdict, namedtuple
from typing import Dict, Iterable, List, Optional

from corehq.apps.fixtures.dbaccessors import (
    get_fixture_data_types_in_domain,
    get_fixture_items_for_data_type,
)
from corehq.apps.fixtures.models import FixtureDataItem

REQUIRED_FIXTURE_DATA_TYPES = (
    'level_1_dcv'
    'level_2_dcv'
    'level_3_dcv'
)
LocationTuple = namedtuple('LocationTuple', [
    'id',
    'name',
    'country',
    'level_1',
    'level_2',
    'level_3',
    'level_4',
])


def get_locations(domain, filters) -> List[LocationTuple]:
    """
    Returns a list of level-four locations, or level-three locations if
    the country does not have level-four locations.

    The return value respects the filters applied by the user.
    """
    data_types_by_tag = get_data_types_by_tag(domain)
    level_1s = get_fixture_dicts(
        domain,
        data_types_by_tag["level_1_dcv"]._id,
        filter_in={
            'id': [filters['level_1']] if filters['level_1'] else None
        }
    )
    l2s_by_l1 = get_fixture_dicts_by_key(
        domain,
        data_type_id=data_types_by_tag["level_2_dcv"]._id,
        key='level_1_dcv',
        filter_in={
            'level_1_dcv': [l['id'] for l in level_1s],
            'id': [filters['level_2']] if filters['level_2'] else None
        }
    )
    l3s_by_l2 = get_fixture_dicts_by_key(
        domain,
        data_type_id=data_types_by_tag["level_3_dcv"]._id,
        key='level_2_dcv',
        filter_in={
            'level_2_dcv': [l2['id'] for l2s in l2s_by_l1 for l2 in l2s],
            'id': [filters['level_3']] if filters['level_3'] else None
        }
    )
    l4_data_items = get_fixture_items_for_data_type(domain, data_types_by_tag["level_4_dcv"]._id)
    country_has_level_4 = len(l4_data_items) > 1
    if country_has_level_4:
        l4s_by_l3 = get_fixture_dicts_by_key(
            domain,
            data_type_id=data_types_by_tag["level_4_dcv"]._id,
            key='level_3_dcv',
            filter_in={
                'level_3_dcv': [l3['id'] for l3s in l3s_by_l2 for l3 in l3s],
                'id': [filters['level_4']] if filters['level_4'] else None
            }
        )
    else:
        l4s_by_l3 = {}

    locations = []
    for level_1 in level_1s:
        for level_2 in l2s_by_l1[level_1['id']]:
            for level_3 in l3s_by_l2[level_2['id']]:
                if country_has_level_4:
                    for level_4 in l4s_by_l3[level_3['id']]:
                        locations.append(LocationTuple(
                            id=level_4['id'],
                            name=level_4['name'],
                            country=level_1['country'],
                            level_1=level_1['name'],
                            level_2=level_2['name'],
                            level_3=level_3['name'],
                            level_4=level_4['name'],
                        ))
                else:
                    locations.append(LocationTuple(
                        id=level_3['id'],
                        name=level_3['name'],
                        country=level_1['country'],
                        level_1=level_1['name'],
                        level_2=level_2['name'],
                        level_3=level_3['name'],
                        level_4=None,
                    ))
    return locations


def get_data_types_by_tag(domain):
    # Not cached, because get_fixture_data_types_in_domain() is already cached
    data_types_by_tag = {
        dt.tag: dt
        for dt in get_fixture_data_types_in_domain(domain)
    }
    for data_type in REQUIRED_FIXTURE_DATA_TYPES:
        assert data_type in data_types_by_tag, \
            f'Domain {domain!r} is missing required lookup table {data_type!r}'
    return data_types_by_tag


def get_fixture_dicts(
    domain: str,
    data_type_id: str,
    filter_in: Optional[Dict[str, Optional[Iterable]]] = None,
) -> List[Dict]:
    """
    Returns a list of fixture data items as dictionaries.

    They can be filtered using ``filter_in``, where if the item has a
    key that is in ``filter_in``, then the value of ``item[key]`` must
    be in the (set/tuple/list) value of ``filter_in[key]``.
    """
    if filter_in is None:
        filter_in = {}
    data_items = get_fixture_items_for_data_type(domain, data_type_id)
    dicts = (fixture_data_item_to_dict(di) for di in data_items)
    return [d for d in dicts if dict_values_in(d, filter_in)]


def get_fixture_dicts_by_key(
    domain: str,
    data_type_id: str,
    key: str,
    filter_in: Optional[Dict[str, list]] = None,
) -> dict:
    """
    Returns a dictionary of fixture data items, keyed on ``key``, and
    fixture data items are dictionaries.

    They can be filtered using ``filter_in``, where if the item has a
    key that is in ``filter_in``, then the value of ``item[key]`` must
    be in the (set/tuple/list) value of ``filter_in[key]``.
    """
    dicts_by_key = defaultdict(list)
    for data_item in get_fixture_items_for_data_type(domain, data_type_id):
        dict_ = fixture_data_item_to_dict(data_item)
        if dict_values_in(dict_, filter_in):
            dicts_by_key[dict_[key]].append(dict_)
    return dicts_by_key


def fixture_data_item_to_dict(
    data_item: FixtureDataItem,
) -> dict:
    """
    Transforms a FixtureDataItem to a dictionary.

    A ``FixtureDataItem.fields`` value looks like this::

        {
            'id': FieldList(
                doc_type='FieldList',
                field_list=[
                    FixtureItemField(
                        doc_type='FixtureItemField',
                        field_value='migori_county',
                        properties={}
                    )
                ]
            ),
            'name': FieldList(
                doc_type='FieldList',
                field_list=[
                    FixtureItemField(
                        doc_type='FixtureItemField',
                        field_value='Migori',
                        properties={'lang': 'en'}
                    )
                ]
            ),
            # ... etc. ...
        }

    Only the first value in each ``FieldList`` is selected.

    .. WARNING:: THIS MEANS THAT TRANSLATIONS ARE NOT SUPPORTED.

    The return value for the example above would be::

        {
            'id': 'migori_county',
            'name': 'Migori'
        }

    """
    return {
        key: field_list.field_list[0].field_value
        for key, field_list in data_item.fields.items()
    }


def dict_values_in(
    dict_: dict,
    key_values: Optional[Dict[str, Optional[Iterable]]] = None,
) -> bool:
    """
    Returns True if ``dict_[key]`` is in ``values`` for all items in
    ``key_values``.

    Also returns True if ``key_values`` is None.

    ``key`` is skipped (i.e. does not return False) if
    ``key_values[key]`` is None.

    >>> swallow = {'permutation': 'unladen'}
    >>> dict_values_in(swallow, {'permutation': ('laden', 'unladen')})
    True
    >>> dict_values_in(swallow, {'permutation': ('African', 'European')})
    False

    """
    if not key_values:
        return True
    for key, values in key_values.items():
        if values is None:
            continue
        if dict_[key] not in values:
            return False
    return True
