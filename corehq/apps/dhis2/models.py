from itertools import chain

import jsonfield
from django.db import models

from corehq.apps.dhis2.utils import get_ucr_data
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


class JsonApiLog(models.Model):
    """
    Store API requests and responses to analyse errors and keep an audit trail
    """
    domain = models.CharField(max_length=126, db_index=True)  # 126 seems to be a popular length
    timestamp = models.DateTimeField()
    request_method = models.CharField(max_length=12)
    request_url = models.CharField(max_length=255)
    request_headers = jsonfield.JSONField(blank=True)
    request_params = jsonfield.JSONField(blank=True)
    request_body = jsonfield.JSONField(blank=True)
    request_error = models.TextField(blank=True)
    response_status = models.IntegerField()
    response_body = models.TextField(blank=True)
