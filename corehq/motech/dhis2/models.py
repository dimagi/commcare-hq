import bz2
from base64 import b64decode, b64encode
from datetime import date, timedelta
from itertools import chain
from typing import List

from django.core.exceptions import ValidationError
from django.db import models

from dateutil.relativedelta import relativedelta

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
from corehq.util.couch import get_document_or_not_found
from corehq.util.quickcache import quickcache

from .const import (
    SEND_FREQUENCIES,
    SEND_FREQUENCY_MONTHLY,
    SEND_FREQUENCY_QUARTERLY,
    SEND_FREQUENCY_WEEKLY,
)


# UNUSED
class Dhis2Connection(models.Model):
    domain = models.CharField(max_length=255, unique=True)
    server_url = models.CharField(max_length=255, null=True)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255, null=True)
    skip_cert_verify = models.BooleanField(default=False)

    @property
    def plaintext_password(self):
        plaintext_bytes = bz2.decompress(b64decode(self.password))
        return plaintext_bytes.decode('utf8')

    @plaintext_password.setter
    def plaintext_password(self, plaintext):
        # Use simple symmetric encryption. We don't need it to be
        # strong, considering we'd have to store the algorithm and the
        # key together anyway; it just shouldn't be plaintext.
        # (2020-03-09) Not true. The key is stored separately.
        plaintext_bytes = plaintext.encode('utf8')
        self.password = b64encode(bz2.compress(plaintext_bytes))

    def save(self, *args, **kwargs):
        raise ValidationError(
            'Dhis2Connection is unused. Use ConnectionSettings instead.'
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

    datavalue_maps = SchemaListProperty(DataValueMap)

    @property
    def connection_settings(self):
        if self.connection_settings_id:
            return ConnectionSettings.objects.get(pk=self.connection_settings_id)


@quickcache(['dataset_map.domain', 'dataset_map.ucr_id'])
def get_datavalue_map_dict(dataset_map: DataSetMap) -> dict:
    dict_ = {dvm.column: dict(dvm, is_org_unit=False, is_period=False) for dvm in dataset_map.datavalue_maps}
    if dataset_map.org_unit_column:
        dict_[dataset_map.org_unit_column] = {'is_org_unit': True, 'is_period': False}
    if dataset_map.period_column:
        dict_[dataset_map.period_column] = {'is_org_unit': False, 'is_period': True}
    return dict_


def get_datavalues(dataset_map: DataSetMap, ucr_row: dict) -> List[dict]:
    """
    Returns rows of "dataElement", "categoryOptionCombo", "value", and
    optionally "period", "orgUnit" and "comment" for ``dataset_map``
    where ``ucr_row`` looks like::

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
    for key, value in ucr_row.items():
        if key in dv_map:
            if dv_map[key]['is_org_unit']:
                org_unit = value
            elif dv_map[key]['is_period']:
                period = value
            else:
                datavalue = {
                    'dataElement': dv_map[key]['data_element_id'],
                    'categoryOptionCombo': dv_map[key]['category_option_combo_id'],
                    'value': value,
                }
                if dv_map[key].get('comment'):
                    datavalue['comment'] = dv_map[key]['comment']
                datavalues.append(datavalue)
    # Second pass is to set period and org unit
    if period or org_unit:
        for datavalue in datavalues:
            if period:
                datavalue['period'] = period
            if org_unit:
                datavalue['orgUnit'] = org_unit
    return datavalues


def get_dataset(dataset_map: DataSetMap, send_date: date) -> dict:
    report_config = get_report_config(dataset_map.domain, dataset_map.ucr_id)
    date_filter = get_date_filter(report_config)

    if dataset_map.frequency == SEND_FREQUENCY_WEEKLY:
        date_range = get_previous_week(send_date)
        period = as_iso_week(date_range)
    elif dataset_map.frequency == SEND_FREQUENCY_MONTHLY:
        date_range = get_previous_month(send_date)
        period = date_range.startdate.strftime('%Y%m')
    elif dataset_map.frequency == SEND_FREQUENCY_QUARTERLY:
        date_range = get_previous_quarter(send_date)
        period = as_iso_quarter(date_range)
    else:
        raise ValueError(f'Unknown frequency {dataset_map.frequency!r}')
    ucr_data = get_ucr_data(report_config, date_filter, date_range)

    datavalues = (get_datavalues(dataset_map, row) for row in ucr_data)  # one UCR row may have many DataValues
    dataset = {
        'dataValues': list(chain.from_iterable(datavalues))  # get a single list of DataValues
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


def as_iso_week(date_span: DateSpan) -> str:
    week_num = int(date_span.startdate.strftime('%W')) + 1
    return f'{date_span.startdate.year}W{week_num}'


def as_iso_quarter(date_span: DateSpan) -> str:
    quarter = (date_span.startdate.month // 3) + 1
    return f'{date_span.startdate.year}Q{quarter}'


def should_send_on_date(dataset_map: DataSetMap, send_date: date) -> bool:
    if dataset_map.frequency == SEND_FREQUENCY_WEEKLY:
        return dataset_map.day_to_send == send_date.isoweekday()
    if dataset_map.frequency == SEND_FREQUENCY_MONTHLY:
        return dataset_map.day_to_send == send_date.day
    if dataset_map.frequency == SEND_FREQUENCY_QUARTERLY:
        return (
            dataset_map.day_to_send == send_date.day
            and send_date.month in [1, 4, 7, 10]
        )


def get_report_config(domain_name, ucr_id):
    report_config = get_document_or_not_found(ReportConfiguration, domain_name, ucr_id)
    return report_config


def get_date_filter(report_config):
    """
    Returns the first date filter, or None.

    Assumes the first date filter is the one to use.

    .. NOTE: The user might not want to filter by date for DHIS2
             integration. They can use a "period" column to return
             rows for multiple periods, or set a period for the report
             if it is always for the same period.
    """
    date_filter = next((f for f in report_config.filters if f['type'] == 'date'), None)
    return date_filter


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
