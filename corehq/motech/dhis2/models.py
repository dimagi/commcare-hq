from __future__ import absolute_import

from __future__ import unicode_literals
from itertools import chain

import jsonfield
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from corehq.motech.dhis2.utils import (
    get_date_filter,
    get_previous_month,
    get_report_config,
    get_ucr_data,
    get_previous_quarter,
)
from corehq.motech.dhis2.const import SEND_FREQUENCY_MONTHLY, SEND_FREQUENCY_QUARTERLY, SEND_FREQUENCIES
from corehq.motech.utils import pformat_json
from corehq.util.quickcache import quickcache
from dimagi.ext.couchdbkit import (
    Document,
    DocumentSchema,
    IntegerProperty,
    SchemaListProperty,
    StringProperty,
)


class Dhis2Connection(Document):
    domain = StringProperty()
    server_url = StringProperty()
    username = StringProperty()
    password = StringProperty()
    log_level = IntegerProperty()


class DataValueMap(DocumentSchema):
    column = StringProperty(required=True)
    data_element_id = StringProperty(required=True)
    category_option_combo_id = StringProperty(required=True)
    comment = StringProperty()


class DataSetMap(Document):
    # domain and UCR uniquely identify a DataSetMap
    domain = StringProperty()
    ucr_id = StringProperty()

    description = StringProperty()
    frequency = StringProperty(choices=SEND_FREQUENCIES, default=SEND_FREQUENCY_MONTHLY)
    day_to_send = IntegerProperty()
    data_set_id = StringProperty()  # If UCR adds values to an existing DataSet
    org_unit_id = StringProperty()  # If all values are for the same OrganisationUnit.
    org_unit_column = StringProperty()  # if not org_unit_id: use org_unit_column
    period = StringProperty()  # If all values are for the same period. Monthly is YYYYMM, quarterly is YYYYQ#
    period_column = StringProperty()  # if not period: use period_column

    attribute_option_combo_id = StringProperty()  # Optional. DHIS2 defaults this to categoryOptionCombo
    complete_date = StringProperty()  # Optional

    datavalue_maps = SchemaListProperty(DataValueMap)

    @quickcache(['self.domain', 'self.ucr_id'])
    def get_datavalue_map_dict(self):
        dict_ = {dvm.column: dict(dvm, is_org_unit=False, is_period=False) for dvm in self.datavalue_maps}
        if self.org_unit_column:
            dict_[self.org_unit_column] = {'is_org_unit': True, 'is_period': False}
        if self.period_column:
            dict_[self.period_column] = {'is_org_unit': False, 'is_period': True}
        return dict_

    def get_datavalues(self, ucr_row):
        """
        Returns rows of "dataElement", "categoryOptionCombo", "value", and optionally "period", "orgUnit" and
        "comment" for this DataSet where ucr_row looks like::

            {
                "org_unit_id": "ABC",
                "data_element_cat_option_combo_1": 123,
                "data_element_cat_option_combo_2": 456,
                "data_element_cat_option_combo_3": 789,
            }

        """
        dv_map = self.get_datavalue_map_dict()
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

    def get_dataset(self, send_date):
        report_config = get_report_config(self.domain, self.ucr_id)
        date_filter = get_date_filter(report_config)

        if self.frequency == SEND_FREQUENCY_MONTHLY:
            date_range = get_previous_month(send_date)
            period = date_range.startdate.strftime('%Y%m')
        elif self.frequency == SEND_FREQUENCY_QUARTERLY:
            date_range = get_previous_quarter(send_date)
            period = date_range.startdate.strftime('%Y') + 'Q' + str((date_range.startdate.month // 3) + 1)
        ucr_data = get_ucr_data(report_config, date_filter, date_range)

        datavalues = (self.get_datavalues(row) for row in ucr_data)  # one UCR row may have many DataValues
        dataset = {
            'dataValues': list(chain.from_iterable(datavalues))  # get a single list of DataValues
        }
        if self.data_set_id:
            dataset['dataSet'] = self.data_set_id
        if self.org_unit_id:
            dataset['orgUnit'] = self.org_unit_id
        if self.period:
            dataset['period'] = self.period
        elif not self.period_column:
            dataset['period'] = period
        if self.attribute_option_combo_id:
            dataset['attributeOptionCombo'] = self.attribute_option_combo_id
        if self.complete_date:
            dataset['completeDate'] = self.complete_date
        return dataset

    def should_send_on_date(self, send_date):
        return self.day_to_send == send_date.day and (
            self.frequency == SEND_FREQUENCY_MONTHLY or
            self.frequency == SEND_FREQUENCY_QUARTERLY and send_date.month in [1, 4, 7, 10])


class JsonApiLog(models.Model):
    """
    Store API requests and responses to analyse errors and keep an audit trail
    """
    domain = models.CharField(max_length=126, db_index=True)  # 126 seems to be a popular length
    timestamp = models.DateTimeField(auto_now_add=True)
    log_level = models.IntegerField(null=True)
    request_method = models.CharField(max_length=12)
    request_url = models.CharField(max_length=255)
    request_headers = jsonfield.JSONField(blank=True)
    request_params = jsonfield.JSONField(blank=True)
    request_body = jsonfield.JSONField(
        blank=True, null=True,  # NULL for GET, but POST can take an empty body
        dump_kwargs={'cls': DjangoJSONEncoder, 'separators': (',', ':')}  # Use DjangoJSONEncoder for dates, etc.
    )
    request_error = models.TextField(null=True)
    response_status = models.IntegerField(null=True)
    response_body = models.TextField(blank=True, null=True)

    @staticmethod
    def log(log_level, json_api_request, request_error, response_status, response_body, method_func, request_url,
            data=None, **params):
        # Don't log credentials
        if 'auth' in params:
            params['auth'] = '******'
        JsonApiLog.objects.create(
            domain=json_api_request.domain_name,
            log_level=log_level,
            request_method=method_func.__name__.upper(),
            request_url=request_url,
            request_headers=json_api_request.headers,
            request_params=params,
            request_body=data,
            request_error=request_error,
            response_status=response_status,
            response_body=response_body,
        )

    @property
    def pp_request_headers(self):
        """
        Pretty-print the request headers
        """
        return pformat_json(self.request_headers)

    @property
    def pp_request_params(self):
        """
        Pretty-print the request params
        """
        return pformat_json(self.request_params)

    @property
    def pp_request_body(self):
        """
        Pretty-print the request body
        """
        return pformat_json(self.request_body)

    @property
    def pp_response_body(self):
        """
        Pretty-print the response body
        """
        return pformat_json(self.response_body)
