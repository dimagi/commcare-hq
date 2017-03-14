import httplib
import json
import logging
from itertools import chain

import requests

from corehq.apps.dhis2.utils import get_ucr_data
from corehq.util.quickcache import quickcache
from dimagi.ext.couchdbkit import (
    DateTimeProperty,
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


class DataValueMap(DocumentSchema):
    column = StringProperty(required=True)
    data_element_id = StringProperty(required=True)
    category_option_combo_id = StringProperty(required=True)
    comment = StringProperty()


class DataSetMap(Document):
    # domain and UCR uniquely identify a DataSetMap
    domain = StringProperty()
    ucr_id = StringProperty()

    day_to_send = IntegerProperty()
    data_set_id = StringProperty()  # If UCR adds values to an existing DataSet
    org_unit_id = StringProperty()  # If all values are for the same OrganisationUnit.
    org_unit_column = StringProperty()  # if not org_unit_id: use org_unit_column
    period = StringProperty()  # If all values are for the same period. MVP: period is monthly, formatted YYYYMM
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
        Returns rows of "dataElementID", "categoryOptionComboID", "value", and optionally "period", "orgUnit" and
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
                        'dataElementID': dv_map[key]['data_element_id'],
                        'categoryOptionComboID': dv_map[key]['category_option_combo_id'],
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

    def get_dataset(self):
        ucr_data = get_ucr_data(self.domain, self.ucr_id)

        dataset = {
            'dataValues': [dv for dv in chain(self.get_datavalues(row) for row in ucr_data)]
        }
        if self.data_set_id:
            dataset['dataSet'] = self.data_set_id
        if self.org_unit_id:
            dataset['orgUnit'] = self.org_unit_id
        if self.period:  # TODO: Should we rather pull this from the report config date range?
            dataset['period'] = self.period
        if self.attribute_option_combo_id:
            dataset['attributeOptionCombo'] = self.attribute_option_combo_id
        if self.complete_date:
            dataset['completeDate'] = self.complete_date
        return dataset


class Dhis2Log(Document):
    """
    Store requests and responses to analyse errors and keep an audit trail
    """
    domain = StringProperty()
    timestamp = DateTimeProperty()
    request_url = StringProperty()
    request_body = StringProperty()
    response_status = IntegerProperty()
    response_body = StringProperty()


class JsonApiError(Exception):
    """
    JsonApiError is raised for HTTP or socket errors.
    """
    pass


class Dhis2ApiQueryError(JsonApiError):
    """
    Dhis2ApiQueryError is raised when the API returns an unexpected response.
    """
    pass


class Dhis2ConfigurationError(Exception):
    """
    DHIS2 API Integration has not been configured correctly.
    """
    pass


class Dhis2IntegrationError(Exception):
    """
    A failure has occurred in CommCareHQ related to but not caused by DHIS2.
    """
    pass


def json_serializer(obj):
    """
    A JSON serializer that serializes dates and times
    """
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()


class JsonApiRequest(object):
    """
    Wrap requests with URL, header and authentication for DHIS2 API
    """

    def __init__(self, server_url, username, password):
        self.server_url = server_url  # e.g. "https://dhis2.example.com/api/26/"
        self.headers = {'Accept': 'application/json'}
        self.auth = (username, password)

    @staticmethod
    def json_or_error(response):
        """
        Return HTTP status, JSON

        :raises JsonApiError: if HTTP status is not in the 200 (OK) range
        """
        if 200 <= response.status_code < 300:
            if response.content:
                return response.json()
            else:
                # Response has no body. Return a status in a way that is consistent with other requests
                return {
                    'status': 'SUCCESS',
                    'httpStatusCode': response.status_code,
                    'httpStatus': httplib.responses[response.status_code],
                }
        else:
            raise JsonApiError('API request to {} failed with HTTP status {}: {}'.format(
                response.url, response.status_code, response.text))

    def get(self, path, **kwargs):
        logging.debug(
            'DHIS2: GET %s: \n'
            '    Headers: %s\n'
            '    kwargs: %s',
            self.server_url + path, self.headers, kwargs
        )
        try:
            response = requests.get(self.server_url + path, headers=self.headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            logging.exception(
                'JSON API raised HTTP or socket error.\n'
                'Request details: %s\n'
                'Error: %s',
                {'method': 'get', 'url': self.server_url + path, 'headers': self.headers},
                err)
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)

    def delete(self, path, **kwargs):
        logging.debug(
            'DHIS2: DELETE %s: \n'
            '    Headers: %s\n'
            '    kwargs: %s',
            self.server_url + path, self.headers, kwargs
        )
        try:
            response = requests.delete(self.server_url + path, headers=self.headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            logging.exception(
                'JSON API raised HTTP or socket error.\n'
                'Request details: %s\n'
                'Error: %s',
                {'method': 'delete', 'url': self.server_url + path, 'headers': self.headers},
                err)
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)

    def post(self, path, data, **kwargs):
        # Make a copy of self.headers because setting content type on requests that don't send content is bad
        headers = self.headers.copy()
        headers['Content-type'] = 'application/json'
        json_data = json.dumps(data, default=json_serializer)
        logging.debug(
            'DHIS2: POST %s: \n'
            '    Headers: %s\n'
            '    Data: %s\n'
            '    kwargs: %s',
            self.server_url + path, self.headers, json_data, kwargs
        )
        try:
            response = requests.post(self.server_url + path, json_data, headers=headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            logging.exception(
                'JSON API raised HTTP or socket error.\n'
                'Request details: %s\n'
                'Error: %s',
                {'method': 'post', 'url': self.server_url + path, 'data': json_data, 'headers': headers},
                err
            )
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)

    def put(self, path, data, **kwargs):
        headers = self.headers.copy()
        headers['Content-type'] = 'application/json'
        json_data = json.dumps(data, default=json_serializer)
        logging.debug(
            'DHIS2: PUT %s: \n'
            '    Headers: %s\n'
            '    Data: %s\n'
            '    kwargs: %s',
            self.server_url + path, self.headers, json_data, kwargs
        )
        try:
            response = requests.put(self.server_url + path, json_data, headers=headers, auth=self.auth, **kwargs)
        except requests.RequestException as err:
            logging.exception(
                'JSON API raised HTTP or socket error.\n'
                'Request details: %s\n'
                'Error: %s',
                {'method': 'put', 'url': self.server_url + path, 'data': json_data, 'headers': headers},
                err
            )
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)
