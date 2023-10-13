from uuid import UUID
from collections import defaultdict, namedtuple
from typing import Any, Dict, Iterable, List, Optional, Tuple

from corehq.apps.fixtures.models import LookupTable, LookupTableRow

REQUIRED_FIXTURE_DATA_TYPES = (
    'level_1_eco',
    'level_2_eco',
    'level_3_eco',
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
    Returns a list of locations, with the user's filters applied.
    """
    level_1s, l2s_by_l1, l3s_by_l2, l4s_by_l3 = get_sorted_levels(domain, filters)

    locations = []
    for level_1 in level_1s:
        for level_2 in l2s_by_l1[level_1['id']]:
            if not l3s_by_l2:
                locations.append(LocationTuple(
                    id=level_2['id'],
                    name=level_2['name'],
                    country=level_1['country'],
                    level_1=level_1['name'],
                    level_2=level_2['name'],
                    level_3=None,
                    level_4=None,
                ))
            else:
                for level_3 in l3s_by_l2[level_2['id']]:
                    if not l4s_by_l3:
                        locations.append(LocationTuple(
                            id=level_3['id'],
                            name=level_3['name'],
                            country=level_1['country'],
                            level_1=level_1['name'],
                            level_2=level_2['name'],
                            level_3=level_3['name'],
                            level_4=None,
                        ))
                    else:
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
    return locations


def get_sorted_levels(domain, filters) -> Tuple[list, dict, dict, dict]:
    """
    Returns dictionaries of location levels, keyed on the ID of their
    parent level. (e.g. {'MA': ['Boston', 'Cambridge']}) The user's
    filters are applied.
    """
    l3s_by_l2 = {}
    l4s_by_l3 = {}
    data_types_by_tag = get_data_type_ids_by_tag(domain)
    level_1s = get_fixture_dicts(
        domain,
        data_types_by_tag["level_1_eco"],
        filter_in={
            'id': [filters['level_1']] if filters['level_1'] else None
        },
        filter_out={'other': '1'},
    )
    l2s_by_l1 = get_fixture_dicts_by_key(
        domain,
        data_type_id=data_types_by_tag["level_2_eco"],
        key='level_1_eco',
        filter_in={
            'level_1_eco': [x['id'] for x in level_1s],
            'id': [filters['level_2']] if filters['level_2'] else None
        },
        filter_out={'other': '1'},
    )
    l3_data_items = get_fixture_items_for_data_type(
        domain, data_types_by_tag["level_3_eco"],
    )
    country_has_level_3 = len(list(l3_data_items)) > 1
    if country_has_level_3:
        l3s_by_l2 = get_fixture_dicts_by_key(
            domain,
            data_type_id=data_types_by_tag["level_3_eco"],
            key='level_2_eco',
            filter_in={
                'level_2_eco': [l2['id'] for l2s in l2s_by_l1.values() for l2 in l2s],
                'id': [filters['level_3']] if filters['level_3'] else None
            },
            filter_out={'other': '1'},
        )
        l4_data_items = get_fixture_items_for_data_type(
            domain, data_types_by_tag["level_4_eco"],
        )
        country_has_level_4 = len(list(l4_data_items)) > 1
        if country_has_level_4:
            l4s_by_l3 = get_fixture_dicts_by_key(
                domain,
                data_type_id=data_types_by_tag["level_4_eco"],
                key='level_3_eco',
                filter_in={
                    'level_3_eco': [l3['id'] for l3s in l3s_by_l2.values() for l3 in l3s],
                    'id': [filters['level_4']] if filters['level_4'] else None
                },
                filter_out={'other': '1'},
            )
    return level_1s, l2s_by_l1, l3s_by_l2, l4s_by_l3


def get_data_type_ids_by_tag(domain):
    ids_by_tag = {
        table.tag: table.id
        for table in LookupTable.objects.by_domain(domain)
    }
    for data_type in REQUIRED_FIXTURE_DATA_TYPES:
        assert data_type in ids_by_tag, \
            f'Domain {domain!r} is missing required lookup table {data_type!r}'
    return ids_by_tag


def get_fixture_dicts(
    domain: str,
    data_type_id: UUID,
    filter_in: Optional[Dict[str, Optional[Iterable]]] = None,
    filter_out: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """
    Returns a list of fixture data items as dictionaries.

    They can be filtered using ``filter_in``, where if the item has a
    key that is in ``filter_in``, then the value of ``item[key]`` must
    be in the (set/tuple/list) value of ``filter_in[key]``.
    """
    data_items = get_fixture_items_for_data_type(domain, data_type_id)
    dicts = (fixture_data_item_to_dict(di) for di in data_items)
    return [d for d in dicts
            if dict_values_in(d, filter_in)
            and dict_value_not(d, filter_out)]


def get_fixture_dicts_by_key(
    domain: str,
    data_type_id: UUID,
    key: str,
    filter_in: Optional[Dict[str, list]] = None,
    filter_out: Optional[Dict[str, Any]] = None,
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
        if (
            dict_values_in(dict_, filter_in)
            and dict_value_not(dict_, filter_out)
        ):
            dicts_by_key[dict_[key]].append(dict_)
    return dicts_by_key


def get_fixture_items_for_data_type(domain, table_id):
    return LookupTableRow.objects.iter_rows(domain, table_id=table_id)


def fixture_data_item_to_dict(data_item: LookupTableRow) -> dict:
    """
    Transforms a LookupTableRow to a dictionary.

    A ``LookupTableRow.fields`` value looks like this::

        {
            'id': [
                    Field(
                        value='migori_county',
                        properties={}
                    )
                ]
            ),
            'name': [
                    Field(
                        value='Migori',
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
        key: field_list[0].value if field_list else None
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


def dict_value_not(
    dict_: dict,
    key_value: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Returns True if ``dict_[key]`` is not ``value`` for key-value pairs
    in ``key_value``.

    >>> swallow = {'mass': 'unladen', 'subspecies': 'European'}
    >>> dict_value_not(swallow, {'subspecies': 'African'})
    True
    >>> swallow = {'mass': 'unladen', 'subspecies': 'African'}
    >>> dict_value_not(swallow, {'subspecies': 'African'})
    False

    """
    if not key_value:
        return True
    for key, value in key_value.items():
        if key in dict_ and dict_[key] == value:
            return False
    return True
