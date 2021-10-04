import copy
from datetime import date, timedelta, datetime
from itertools import chain
from typing import Dict, List, Optional, Union

from django.db import models
from django.forms import model_to_dict

from dateutil.relativedelta import relativedelta
from memoized import memoized_property

from dimagi.ext.couchdbkit import (
    Document,
    DocumentSchema,
    IntegerProperty,
    SchemaListProperty,
    StringProperty,
)
from dimagi.utils.dates import DateSpan

from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.reports.data_source import (
    ConfigurableReportDataSource,
)
from corehq.motech.models import ConnectionSettings
from corehq.util.couch import DocumentNotFound, get_document_or_not_found
from corehq.util.quickcache import quickcache

from .const import (
    SEND_FREQUENCIES,
    SEND_FREQUENCY_CHOICES,
    SEND_FREQUENCY_MONTHLY,
    SEND_FREQUENCY_QUARTERLY,
    SEND_FREQUENCY_WEEKLY,
    COMPLETE_DATE_CHOICES,
    COMPLETE_DATE_EMPTY,
    COMPLETE_DATE_ON_PERIOD_END,
    COMPLETE_DATE_ON_SEND,
)


class DataValueMap(DocumentSchema):
    column = StringProperty(required=True)
    data_element_id = StringProperty(required=True)
    category_option_combo_id = StringProperty(required=True)
    comment = StringProperty()


class DataSetMap(Document):
    # domain and UCR uniquely identify a DataSetMap
    domain = StringProperty()
    connection_settings_id = IntegerProperty(required=False, default=None)
    ucr_id = StringProperty()  # UCR ReportConfig id

    description = StringProperty()
    frequency = StringProperty(choices=SEND_FREQUENCIES, default=SEND_FREQUENCY_MONTHLY)
    # Day of the month for monthly/quarterly frequency. Day of the week
    # for weekly frequency. Uses ISO-8601, where Monday = 1, Sunday = 7.
    day_to_send = IntegerProperty()
    data_set_id = StringProperty()  # If UCR adds values to an existing DataSet
    org_unit_id = StringProperty()  # If all values are for the same OrganisationUnit.
    org_unit_column = StringProperty()  # if not org_unit_id: use org_unit_column
    period = StringProperty()  # If all values are for the same period. Monthly is YYYYMM, quarterly is YYYYQ#
    period_column = StringProperty()  # if not period: use period_column

    attribute_option_combo_id = StringProperty()  # Optional. DHIS2 defaults this to categoryOptionCombo
    complete_date = StringProperty()  # Optional
    complete_date_option = StringProperty(
        default=COMPLETE_DATE_EMPTY,
        choices=COMPLETE_DATE_CHOICES,
    )
    complete_date_column = StringProperty()  # Optional

    datavalue_maps = SchemaListProperty(DataValueMap)

    @property
    def connection_settings(self):
        if self.connection_settings_id:
            return ConnectionSettings.objects.get(pk=self.connection_settings_id)

    @property
    def pk(self):
        return self._id


class SQLDataSetMap(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    couch_id = models.CharField(max_length=36, null=True, blank=True,
                                db_index=True)
    connection_settings = models.ForeignKey(ConnectionSettings,
                                            on_delete=models.PROTECT,
                                            null=True, blank=True)
    ucr_id = models.CharField(max_length=36)
    description = models.TextField()
    frequency = models.CharField(max_length=16,
                                 choices=SEND_FREQUENCY_CHOICES,
                                 default=SEND_FREQUENCY_MONTHLY)

    # Day of the month for monthly/quarterly frequency. Day of the week
    # for weekly frequency. Uses ISO-8601, where Monday = 1, Sunday = 7.
    day_to_send = models.PositiveIntegerField()

    data_set_id = models.CharField(max_length=11, null=True, blank=True)

    org_unit_id = models.CharField(max_length=11, null=True, blank=True)
    org_unit_column = models.CharField(max_length=64, null=True, blank=True)

    # cf. https://docs.dhis2.org/master/en/developer/html/webapi_date_perid_format.html
    period = models.CharField(max_length=32, null=True, blank=True)
    period_column = models.CharField(max_length=64, null=True, blank=True)

    attribute_option_combo_id = models.CharField(max_length=11,
                                                 null=True, blank=True)
    complete_date = models.DateField(null=True, blank=True)
    complete_date_option = models.CharField(
        max_length=64,
        default=COMPLETE_DATE_EMPTY,
        choices=COMPLETE_DATE_CHOICES,
    )
    complete_date_column = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        return self.description

    @memoized_property
    def ucr(self) -> Optional[ReportConfiguration]:
        try:
            return get_document_or_not_found(ReportConfiguration,
                                             self.domain, self.ucr_id)
        except DocumentNotFound:
            return None


class SQLDataValueMap(models.Model):
    dataset_map = models.ForeignKey(
        SQLDataSetMap, on_delete=models.CASCADE,
        related_name='datavalue_maps',
    )
    column = models.CharField(max_length=64)
    data_element_id = models.CharField(max_length=11)
    category_option_combo_id = models.CharField(max_length=11, blank=True)
    comment = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.column


@quickcache(['dataset_map.domain', 'dataset_map.pk'])
def get_info_for_columns(
    dataset_map: Union[DataSetMap, SQLDataSetMap],
) -> Dict[str, dict]:

    info_for_columns = {
        dvm.column: {
            **_datavalue_map_to_dict(dvm),
            'is_org_unit': False,
            'is_period': False,
            'is_complete_date': False,
        }
        for dvm in _iter_datavalue_maps(dataset_map)
    }
    if dataset_map.org_unit_column:
        info_for_columns[dataset_map.org_unit_column] = {
            'is_org_unit': True,
            'is_period': False,
            'is_complete_date': False,
        }
    if dataset_map.period_column:
        info_for_columns[dataset_map.period_column] = {
            'is_org_unit': False,
            'is_period': True,
            'is_complete_date': False,
        }
    if dataset_map.complete_date_column:
        info_for_columns[dataset_map.complete_date_column] = {
            'is_org_unit': False,
            'is_period': False,
            'is_complete_date': True,
        }

    return info_for_columns


def _datavalue_map_to_dict(datavalue_map):
    try:
        return model_to_dict(datavalue_map, exclude=['id', 'dataset_map'])
    except AttributeError:
        return datavalue_map


def _iter_datavalue_maps(dataset_map):
    try:
        return dataset_map.datavalue_maps.all()
    except AttributeError:
        return dataset_map.datavalue_maps


def get_datavalues(
    dataset_map: Union[DataSetMap, SQLDataSetMap],
    ucr_row: dict,
) -> List[dict]:
    """
    Given a ``ucr_row`` that looks like ... ::

        {
            "org_unit_id": "ghi45678901",
            "data_element_cat_option_combo_1": 123,
            "data_element_cat_option_combo_2": 456,
            "data_element_cat_option_combo_3": 789,
        }

    ... returns rows of data values that look like ::

        {
            "dataElement": "abc45678901",
            "value": 123,
            "categoryOptionCombo": "def45678901",  /* optional */
            "period": 202101,  /* optional */
            "orgUnit": "ghi45678901",  /* optional */
            "comment": "A comment"  /* optional */
        }

    """
    info_for_columns = get_info_for_columns(dataset_map)

    datavalues = []
    org_unit = None
    period = None
    complete_date = None

    # First pass is to collate data element IDs and values
    for key, value in ucr_row.items():
        if key in info_for_columns:
            if info_for_columns[key]['is_org_unit']:
                org_unit = value
            elif info_for_columns[key]['is_period']:
                period = value
            elif info_for_columns[key]['is_complete_date']:
                complete_date = value
            else:
                datavalue = {
                    'dataElement': info_for_columns[key]['data_element_id'],
                    'value': value,
                }
                if info_for_columns[key].get('category_option_combo_id'):
                    datavalue['categoryOptionCombo'] = (
                        info_for_columns[key]['category_option_combo_id'])
                if info_for_columns[key].get('comment'):
                    datavalue['comment'] = info_for_columns[key]['comment']
                datavalues.append(datavalue)
    # Second pass is to set period, org unit and complete date
    if period or org_unit or complete_date:
        determine_complete_date_on_period_end = dataset_map.complete_date_option == COMPLETE_DATE_ON_PERIOD_END

        for datavalue in datavalues:
            if period:
                datavalue['period'] = period
                if determine_complete_date_on_period_end:
                    datavalue['completeDate'] = str(get_end_of_period(dataset_map.frequency, period))

            if org_unit:
                datavalue['orgUnit'] = org_unit

            # This implies dataset_map.complete_date_option == COMPLETE_DATE_COLUMN
            if complete_date:
                datavalue['completeDate'] = complete_date
    return datavalues


def parse_dataset_for_request(
    dataset_map: Union[DataSetMap, SQLDataSetMap],
    send_date: date
) -> list:
    if not dataset_map.ucr:
        raise ValueError(f'UCR not found for {dataset_map!r}')
    date_filter = get_date_filter(dataset_map.ucr)
    date_range = get_date_range(dataset_map.frequency, send_date)
    ucr_data = get_ucr_data(dataset_map.ucr, date_filter, date_range)

    datavalues = (get_datavalues(dataset_map, row) for row in ucr_data)  # one UCR row may have many DataValues
    datavalues_list = list(chain.from_iterable(datavalues))  # get a single list of DataValues

    dataset = {}

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

    (dataset, should_group_data) = evaluate_complete_date(dataset_map, dataset, send_date)

    if should_group_data:
        return group_dataset_datavalues(dataset, datavalues_list)
    else:
        dataset['dataValues'] = datavalues_list
        return [dataset]


def evaluate_complete_date(
    dataset_map: SQLDataSetMap,
    dataset: dict,
    send_date: date,
):
    if dataset_map.complete_date_option == COMPLETE_DATE_EMPTY:
        return dataset, False

    if dataset_map.complete_date_option == COMPLETE_DATE_ON_SEND:
        dataset['completeDate'] = str(send_date)

    if dataset_map.complete_date_option == COMPLETE_DATE_ON_PERIOD_END and dataset_map.period:
        dataset['completeDate'] = str(get_end_of_period(dataset_map.frequency, dataset_map.period))

    return dataset, True


def group_dataset_datavalues(
    dataset,
    datavalues_list
) -> list:
    """
     The 'period' and 'orgUnit' must be specified when the 'completeDate' is specified (and on
     the same level) such that the payload obeys the following format:
        {
            "completeDate": <completeDate>,
            "orgUnit": <orgUnit>,
            "period": <period>,
            "dataValues": [...]
        }

    The problem is that either one or more of the 'period', 'orgUnit' or 'completeDate' key-value pairs
    could be specified in the datavalues list (not on the dataset top level). We need to extract these
    and group the data accordingly.

    We can do a simple check to see which keys ('period', 'orgUnit' or 'completeDate') is not already
    specified on the dataset top level. If any keys are missing that means that we have to group all
    the datavalues by the specific key(s) such that the payload(s) returned obeys the structure above
    and the values are relevant to each other.
    """

    dataset_keys = dataset.keys()
    necessary_dataset_keys = ['orgUnit', 'period', 'completeDate']
    group_by_keys = []

    [group_by_keys.append(key) for key in necessary_dataset_keys if key not in dataset_keys]

    if not group_by_keys:
        dataset['dataValues'] = datavalues_list
        return [dataset]
    else:
        return get_grouped_datavalues_sets(
            data_list=datavalues_list,
            group_by_keys=group_by_keys,
            template_dataset=dataset
        )


def _group_data_by_keys(data: List[dict], keys: list):
    from collections import defaultdict
    datasets_dict = defaultdict(lambda: [])

    for row in data:
        dict_key = []
        for k in keys:
            dict_key.append(row[k])
            row.pop(k)

        dict_key = tuple(dict_key)
        datasets_dict[dict_key].append(row)

    return dict(datasets_dict)


def get_grouped_datavalues_sets(
    data_list: List[dict],
    group_by_keys: list,
    template_dataset: dict,
) -> List[dict]:

    datasets = []
    for grouped_key, grouped_value in _group_data_by_keys(data_list, group_by_keys).items():
        dataset = copy.deepcopy(template_dataset)

        for key, key_value in zip(group_by_keys, grouped_key):
            dataset[key] = key_value

        dataset['dataValues'] = grouped_value
        datasets.append(dataset)

    return datasets


def get_date_range(frequency: str, send_date: date) -> DateSpan:
    if frequency == SEND_FREQUENCY_WEEKLY:
        return get_previous_week(send_date)
    elif frequency == SEND_FREQUENCY_MONTHLY:
        return get_previous_month(send_date)
    elif frequency == SEND_FREQUENCY_QUARTERLY:
        return get_previous_quarter(send_date)
    else:
        raise ValueError(f'Unknown frequency {frequency!r}')


def get_period(frequency: str, startdate: date) -> str:
    if frequency == SEND_FREQUENCY_WEEKLY:
        return as_iso_week(startdate)
    elif frequency == SEND_FREQUENCY_MONTHLY:
        return startdate.strftime('%Y%m')
    elif frequency == SEND_FREQUENCY_QUARTERLY:
        return as_iso_quarter(startdate)
    else:
        raise ValueError(f'Unknown frequency {frequency!r}')


def as_iso_week(startdate: date) -> str:
    week_num = int(startdate.strftime('%W')) + 1
    return f'{startdate.year}W{week_num}'


def as_iso_quarter(startdate: date) -> str:
    quarter = (startdate.month // 3) + 1
    return f'{startdate.year}Q{quarter}'


def should_send_on_date(
    dataset_map: Union[DataSetMap, SQLDataSetMap],
    send_date: date,
) -> bool:
    if dataset_map.frequency == SEND_FREQUENCY_WEEKLY:
        return dataset_map.day_to_send == send_date.isoweekday()
    if dataset_map.frequency == SEND_FREQUENCY_MONTHLY:
        return dataset_map.day_to_send == send_date.day
    if dataset_map.frequency == SEND_FREQUENCY_QUARTERLY:
        return (
            dataset_map.day_to_send == send_date.day
            and send_date.month in [1, 4, 7, 10]
        )


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


def get_previous_week(send_date: date) -> DateSpan:
    """
    Returns a DateSpan from last week Monday to last week Sunday

    ISO 8601 has Monday as Day 1 and Sunday as Day 7
    """
    # monday.weekday() == 0, so subtracting send_date.weekday() from
    # send_date will always give you the Monday at the start of the week
    monday = send_date - timedelta(days=send_date.weekday())
    startdate = monday - timedelta(days=7)
    enddate = monday - timedelta(days=1)
    return DateSpan(startdate, enddate)


def get_previous_month(send_date):
    enddate = date(year=send_date.year, month=send_date.month, day=1) - timedelta(days=1)
    startdate = date(year=enddate.year, month=enddate.month, day=1)
    return DateSpan(startdate, enddate)


def get_previous_quarter(send_date):
    start_month = get_quarter_start_month(send_date.month)
    startdate = (date(year=send_date.year, month=start_month, day=1)
                 - relativedelta(months=3))
    enddate = (date(year=send_date.year, month=start_month, day=1)
               - timedelta(days=1))
    return DateSpan(startdate, enddate)


def get_quarter_start_month(month):
    return (((month - 1) // 3) * 3) + 1


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


def get_ucr_data(report_config, date_filter, date_span):
    from corehq.apps.userreports.reports.view import get_filter_values

    data_source = ConfigurableReportDataSource.from_spec(report_config, include_prefilters=True)

    filter_params = get_date_params(date_filter['slug'], date_span) if date_filter else {}
    filter_values = get_filter_values(report_config.ui_filters, filter_params)
    data_source.set_filter_values(filter_values)
    return data_source.get_data()


def get_end_of_period(frequency, period):
    """
    period = "2004W10" for week 10, 2004, frequency = SEND_FREQUENCY_WEEKLY.
    period = "200403" for March 2004, frequency = SEND_FREQUENCY_MONTHLY.
    period = "2004Q1" for January-March 2004, frequency = SEND_FREQUENCY_QUARTERLY
    """

    if frequency == SEND_FREQUENCY_WEEKLY:
        (year, week) = period.split('W')
        start_of_year = datetime(int(year), 1, 1)
        days_in_n_weeks = int(week) * 7
        end_of_period = start_of_year + relativedelta(days=days_in_n_weeks)

    elif frequency == SEND_FREQUENCY_MONTHLY:
        year = period[0:4]  # '2004' in '200403'
        month = period[4:7]  # '03' in '200403'
        start_of_year = datetime(int(year), 1, 1)
        end_of_period = start_of_year + relativedelta(months=int(month))

    elif frequency == SEND_FREQUENCY_QUARTERLY:
        (year, quarter) = period.split('Q')
        start_of_year = datetime(int(year), 1, 1)
        months = int(quarter) * 3
        end_of_period = start_of_year + relativedelta(months=months)
    else:
        return None

    # Subtract 1 day for last day of month/week instead of 1st day of
    # next month/week
    return (end_of_period - relativedelta(days=1)).date()
