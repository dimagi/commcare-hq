from datetime import date, datetime, timedelta
from itertools import chain
from typing import List

from celery.schedules import crontab
from celery.task import periodic_task, task
from dateutil.relativedelta import relativedelta

from dimagi.utils.dates import DateSpan
from toggle.shortcuts import find_domains_with_toggle_enabled

from corehq import toggles
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.data_source import (
    ConfigurableReportDataSource,
)
from corehq.motech.dhis2.const import (
    SEND_FREQUENCY_MONTHLY,
    SEND_FREQUENCY_QUARTERLY,
    SEND_FREQUENCY_WEEKLY,
)
from corehq.motech.dhis2.dbaccessors import get_dataset_maps
from corehq.util.couch import get_document_or_not_found


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
    date_range = get_date_range(dataset_map.frequency, send_date)
    ucr_data = get_ucr_data(report_config, date_filter, date_range)

    info_for_columns = get_info_for_columns(dataset_map)
    # one UCR row may have many DataValues
    datavalues = (get_datavalues(info_for_columns, row) for row in ucr_data)
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
        dataset['period'] = get_period(dataset_map.frequency,
                                       date_range.startdate)
    if dataset_map.attribute_option_combo_id:
        dataset['attributeOptionCombo'] = dataset_map.attribute_option_combo_id
    if dataset_map.complete_date:
        dataset['completeDate'] = dataset_map.complete_date
    return dataset


def get_datavalues(info_for_columns: dict, ucr_row: dict) -> List[dict]:
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
    datavalues = []
    org_unit = None
    period = None
    # First pass is to collate data element IDs and values
    for column, value in ucr_row.items():
        if column in info_for_columns:
            colinfo = info_for_columns[column]
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


def get_info_for_columns(dataset_map):
    info_for_columns = {
        dvm.column: {**dvm, 'is_org_unit': False, 'is_period': False}
        for dvm in dataset_map.datavalue_maps
    }
    if dataset_map.org_unit_column:
        info_for_columns[dataset_map.org_unit_column] = {
            'is_org_unit': True,
            'is_period': False,
        }
    if dataset_map.period_column:
        info_for_columns[dataset_map.period_column] = {
            'is_org_unit': False,
            'is_period': True,
        }
    return info_for_columns


def get_report_config(domain_name, ucr_id):
    return get_document_or_not_found(ReportConfiguration, domain_name, ucr_id)


def get_date_filter(report_config):
    """
    Returns the first date filter, or None.

    Assumes the first date filter is the one to use.

    .. NOTE: The user might not want to filter by date for DHIS2
             integration. They can use a "period" column to return
             rows for multiple periods, or set a period for the report
             if it is always for the same period.
    """
    return next((f for f in report_config.filters if f['type'] == 'date'), None)


def get_date_range(frequency: str, send_date: date) -> DateSpan:
    if frequency == SEND_FREQUENCY_WEEKLY:
        return get_previous_week(send_date)
    if frequency == SEND_FREQUENCY_MONTHLY:
        return get_previous_month(send_date)
    if frequency == SEND_FREQUENCY_QUARTERLY:
        return get_previous_quarter(send_date)
    raise ValueError(f'Unknown frequency {frequency!r}')


def get_previous_week(send_date: date) -> DateSpan:
    """
    Returns a DateSpan from last week Monday to last week Sunday

    ISO 8601 has Monday as Day 1 and Sunday as Day 7
    """
    # monday.weekday() == 0
    monday = send_date - timedelta(days=send_date.weekday())
    startdate = monday - timedelta(days=7)
    enddate = monday - timedelta(days=1)
    return DateSpan(startdate, enddate)


def get_previous_month(send_date: date) -> DateSpan:
    enddate = (date(year=send_date.year, month=send_date.month, day=1)
               - timedelta(days=1))
    startdate = date(year=enddate.year, month=enddate.month, day=1)
    return DateSpan(startdate, enddate)


def get_previous_quarter(send_date: date) -> DateSpan:
    current_quarter_start = (((send_date.month - 1) // 3) * 3) + 1
    startdate = (date(year=send_date.year, month=current_quarter_start, day=1)
                 - relativedelta(months=3))
    enddate = (date(year=send_date.year, month=current_quarter_start, day=1)
               - timedelta(days=1))
    return DateSpan(startdate, enddate)


def get_period(frequency: str, startdate: date) -> str:
    if frequency == SEND_FREQUENCY_WEEKLY:
        week_num = int(startdate.strftime('%W')) + 1
        return startdate.strftime('%Y') + f'W{week_num}'

    if frequency == SEND_FREQUENCY_MONTHLY:
        return startdate.strftime('%Y%m')

    if frequency == SEND_FREQUENCY_QUARTERLY:
        quarter = (startdate.month - 1) // 3 + 1
        return startdate.strftime('%Y') + f'Q{quarter}'

    raise ValueError(f'Unknown frequency {frequency!r}')


def get_ucr_data(report_config, date_filter, date_span):
    from corehq.apps.userreports.reports.view import get_filter_values

    data_source = ConfigurableReportDataSource.from_spec(
        report_config, include_prefilters=True)

    filter_params = get_date_params(date_filter['slug'], date_span) if date_filter else {}
    filter_values = get_filter_values(report_config.ui_filters, filter_params)
    data_source.set_filter_values(filter_values)
    return data_source.get_data()


def get_date_params(slug, date_span):
    """
    Mimics date filter request parameters
    """
    startdate = date_span.startdate.strftime('%Y-%m-%d')
    enddate = date_span.enddate.strftime('%Y-%m-%d')
    return {
        slug: "{}+to+{}".format(startdate, enddate),
        slug + '-start': startdate,
        slug + '-end': enddate,
    }
