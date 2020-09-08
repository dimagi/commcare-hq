from datetime import datetime
from itertools import chain

from celery.schedules import crontab
from celery.task import periodic_task, task

from toggle.shortcuts import find_domains_with_toggle_enabled

from corehq import toggles
from corehq.motech.dhis2.const import (
    SEND_FREQUENCY_MONTHLY,
    SEND_FREQUENCY_QUARTERLY,
    SEND_FREQUENCY_WEEKLY,
)
from corehq.motech.dhis2.dbaccessors import get_dataset_maps
from corehq.motech.dhis2.utils import (
    get_date_filter,
    get_previous_month,
    get_previous_quarter,
    get_report_config,
    get_ucr_data,
)
from corehq.util.quickcache import quickcache


@periodic_task(
    run_every=crontab(minute=3, hour=3),
    queue='background_queue'
)
def send_datasets_for_all_domains():
    for domain_name in find_domains_with_toggle_enabled(toggles.DHIS2_INTEGRATION):
        send_datasets(domain_name)


@task(serializer='pickle', queue='background_queue')
def send_datasets(domain_name, send_now=False, send_date=None):
    """
    Sends a data set of data values in the following format:

    {
      "dataSet": "dataSetID",
      "completeDate": "date",
      "period": "period",
      "orgUnit": "orgUnitID",
      "attributeOptionCombo", "aocID",
      "dataValues": [
        { "dataElement": "dataElementID", "categoryOptionCombo": "cocID", "value": "1", "comment": "comment1" },
        { "dataElement": "dataElementID", "categoryOptionCombo": "cocID", "value": "2", "comment": "comment2" },
        { "dataElement": "dataElementID", "categoryOptionCombo": "cocID", "value": "3", "comment": "comment3" }
      ]
    }

    See DHIS2 API docs for more details: https://docs.dhis2.org/master/en/developer/html/webapi_data_values.html

    """
    if not send_date:
        send_date = datetime.today()
    dataset_maps = get_dataset_maps(domain_name)
    if not dataset_maps:
        return  # Nothing to do
    for dataset_map in dataset_maps:
        if send_now or should_send_on_date(dataset_map, send_date):
            conn = dataset_map.connection_settings
            dataset = get_dataset(dataset_map, send_date)
            with conn.get_requests() as requests:
                requests.post('/api/dataValueSets', json=dataset)


def should_send_on_date(dataset_map, send_date):
    if dataset_map.frequency == SEND_FREQUENCY_WEEKLY:
        return dataset_map.day_to_send == send_date.isoweekday()
    if dataset_map.frequency == SEND_FREQUENCY_MONTHLY:
        return dataset_map.day_to_send == send_date.day
    if dataset_map.frequency == SEND_FREQUENCY_QUARTERLY:
        return (
            dataset_map.day_to_send == send_date.day
            and send_date.month in [1, 4, 7, 10]
        )


def get_dataset(dataset_map, send_date):
    report_config = get_report_config(dataset_map.domain, dataset_map.ucr_id)
    date_filter = get_date_filter(report_config)

    if dataset_map.frequency == SEND_FREQUENCY_MONTHLY:
        date_range = get_previous_month(send_date)
        period = date_range.startdate.strftime('%Y%m')
    elif dataset_map.frequency == SEND_FREQUENCY_QUARTERLY:
        date_range = get_previous_quarter(send_date)
        period = date_range.startdate.strftime('%Y') + 'Q' + str((date_range.startdate.month // 3) + 1)
    # TODO: WHOA! What about SEND_FREQUENCY_WEEKLY?!
    ucr_data = get_ucr_data(report_config, date_filter, date_range)

    # one UCR row may have many DataValues
    datavalues = (get_datavalues(dataset_map, row) for row in ucr_data)
    dataset = {
        # get a single list of DataValues
        'dataValues': list(chain.from_iterable(datavalues))
    }
    if dataset_map.data_set_id:
        dataset['dataSet'] = dataset_map.data_set_id
    if dataset_map.org_unit_id:
        dataset['orgUnit'] = dataset_map.org_unit_id
    if dataset_map.period:
        dataset['period'] = dataset_map.period
    elif not dataset_map.period_column:
        dataset['period'] = period
    if dataset_map.attribute_option_combo_id:
        dataset['attributeOptionCombo'] = dataset_map.attribute_option_combo_id
    if dataset_map.complete_date:
        dataset['completeDate'] = dataset_map.complete_date
    return dataset


@quickcache(['dataset_map.domain', 'dataset_map.ucr_id'])
def get_datavalue_map_dict(dataset_map):
    dict_ = {dvm.column: dict(dvm, is_org_unit=False, is_period=False)
             for dvm in dataset_map.datavalue_maps}
    if dataset_map.org_unit_column:
        dict_[dataset_map.org_unit_column] = {
            'is_org_unit': True,
            'is_period': False,
        }
    if dataset_map.period_column:
        dict_[dataset_map.period_column] = {
            'is_org_unit': False,
            'is_period': True,
        }
    return dict_


def get_datavalues(dataset_map, ucr_row):
    """
    Returns rows of "dataElement", "categoryOptionCombo", "value", and
    optionally "period", "orgUnit" and "comment" for this DataSet where
    ucr_row looks like::

        {
            "org_unit_id": "ABC",
            "data_element_cat_option_combo_1": 123,
            "data_element_cat_option_combo_2": 456,
            "data_element_cat_option_combo_3": 789,
        }

    """
    dv_map = get_datavalue_map_dict(dataset_map)
    datavalues = []
    org_unit = None
    period = None
    # First pass is to collate data element IDs and values
    for column, value in ucr_row.items():
        if column in dv_map:
            colinfo = dv_map[column]
            if colinfo['is_org_unit']:
                org_unit = value
            elif colinfo['is_period']:
                period = value
            else:
                datavalue = {
                    'dataElement': colinfo['data_element_id'],
                    'categoryOptionCombo': colinfo['category_option_combo_id'],
                    'value': value,
                }
                if colinfo.get('comment'):
                    datavalue['comment'] = colinfo['comment']
                datavalues.append(datavalue)
    # Second pass is to set period and org unit
    if period or org_unit:
        for datavalue in datavalues:
            if period:
                datavalue['period'] = period
            if org_unit:
                datavalue['orgUnit'] = org_unit
    return datavalues
