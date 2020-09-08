import re
from datetime import date
from typing import Optional

from corehq.util.quickcache import quickcache


@quickcache(['domain_name'])
def get_dataset_maps(domain_name):
    from corehq.motech.dhis2.models import SQLDataSetMap

    dataset_maps = (SQLDataSetMap.objects
                    .filter(domain=domain_name)
                    .select_related('datavalue_maps',
                                    'connection_settings'))
    if not dataset_maps:
        dataset_maps = get_migrated_dataset_maps(domain_name)
    return dataset_maps


def get_migrated_dataset_maps(domain: str):
    from corehq.motech.dhis2.models import SQLDataSetMap, SQLDataValueMap
    from corehq.motech.models import ConnectionSettings

    connx = {}

    def get_connx(connx_id):
        nonlocal connx
        if connx_id is None:
            return None
        if connx_id not in connx:
            connx[connx_id] = ConnectionSettings.objects.get(pk=connx_id)
        return connx[connx_id]

    migrated_dataset_maps = []
    for dataset_map in get_couch_dataset_maps(domain):
        sql_dataset_map = SQLDataSetMap.objects.create(
            domain=dataset_map.domain,
            connection_settings=get_connx(dataset_map.connection_settings_id),
            ucr_id=dataset_map.ucr_id,
            description=dataset_map.description,
            frequency=dataset_map.frequency,
            day_to_send=dataset_map.day_to_send,
            data_set_id=dataset_map.data_set_id or None,
            org_unit_id=dataset_map.org_unit_id or None,
            org_unit_column=dataset_map.org_unit_column or None,
            period=dataset_map.period or None,
            period_column=dataset_map.period_column or None,
            attribute_option_combo_id=(
                dataset_map.attribute_option_combo_id or None),
            complete_date=as_date_or_none(dataset_map.complete_date)
        )
        for dv_map in dataset_map.datavalue_maps:
            SQLDataValueMap.objects.create(
                dataset_map=sql_dataset_map,
                column=dv_map.column,
                data_element_id=dv_map.data_element_id,
                category_option_combo_id=dv_map.category_option_combo_id,
                comment=dv_map.comment,
            )
        migrated_dataset_maps.append(sql_dataset_map)
    return migrated_dataset_maps


def as_date_or_none(iso_date: Optional[str]) -> Optional[date]:
    """
    Casts an ISO-formatted date string as a datetime.date, or None if it
    is blank.

    >>> as_date_or_none('2020-11-03')
    datetime.date(2020, 11, 4)
    >>> as_date_or_none('')
    None
    >>> as_date_or_none(None)
    None

    """
    if not iso_date:
        return None
    if not re.match(r'\d{4}-\d{2}-\d{2}', iso_date):
        raise ValueError(f'{iso_date!r} is not an ISO-8601-formatted date')
    year, month, day = map(int, iso_date.split('-'))
    return date(year, month, day)


@quickcache(['domain_name'])
def get_couch_dataset_maps(domain_name):
    from corehq.motech.dhis2.models import DataSetMap

    results = DataSetMap.get_db().view(
        'by_domain_doc_type_date/view',
        key=[domain_name, 'DataSetMap', None],
        include_docs=True,
        reduce=False,
    ).all()
    return [DataSetMap.wrap(result['doc']) for result in results]
