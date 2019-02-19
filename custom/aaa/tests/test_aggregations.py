from __future__ import absolute_import, unicode_literals

import os
import re
from datetime import date, time
from decimal import Decimal

import six
from django.test.testcases import override_settings

from custom.aaa.models import (
    AggAwc,
    AggVillage,
    CcsRecord,
    Child,
    Woman,
)
from custom.aaa.tasks import (
    update_agg_awc_table,
    update_agg_village_table,
    update_ccs_record_table,
    update_child_table,
    update_woman_table,
)
from custom.aaa.tests import OUTPUT_PATH, TEST_DOMAIN
from custom.icds_reports.tests import CSVTestCase


@override_settings(SERVER_ENVIRONMENT='icds')
class AggregationScriptTestBase(CSVTestCase):
    always_include_columns = None

    @classmethod
    def setUpClass(cls):
        super(AggregationScriptTestBase, cls).setUpClass()
        update_child_table(TEST_DOMAIN)
        update_woman_table(TEST_DOMAIN)
        update_ccs_record_table(TEST_DOMAIN)

        for month in range(1, 3):
            update_agg_awc_table(TEST_DOMAIN, date(2019, month, 1))
            update_agg_village_table(TEST_DOMAIN, date(2019, month, 1))

    def _convert_decimal_to_string(self, value):
        """
            Args:
                value (decimal.Decimal)
            Returns:
                str
            Converts scientific notation to decimal form if needed.
            it's needed because in csv file all numbers are written in decimal form.
            Here is an example why we can't simply apply str to decimal number
                >>> str(Decimal('0.0000000'))
                '0E-7'
                >>> self._convert_decimal_to_string(Decimal('0.0000000'))
                '0.0000000'
        """
        value_str = str(value)
        p = re.compile('0E-(?P<zeros>[0-9]+)')
        match = p.match(value_str)
        if match:
            return '0.{}'.format(int(match.group('zeros')) * '0')
        else:
            return value_str

    def _load_data_from_db(self, table_cls, sort_key):
        for row in table_cls.objects.order_by(*sort_key).values().all():
            for key, value in list(row.items()):
                if isinstance(value, date):
                    row[key] = value.strftime('%Y-%m-%d')
                elif isinstance(value, time):
                    row[key] = value.strftime("%H:%M:%S.%f").rstrip('0').rstrip('.')
                elif isinstance(value, six.integer_types):
                    row[key] = str(value)
                elif isinstance(value, (float, Decimal)):
                    row[key] = self._convert_decimal_to_string(row[idx])
                elif isinstance(value, six.string_types):
                    row[key] = value.encode('utf-8')
                elif value is None:
                    row[key] = ''
            yield row

    def _load_and_compare_data(self, table_name, path, sort_key=None):
        self._fasterAssertListEqual(
            list(self._load_data_from_db(table_name, sort_key)),
            self._load_csv(path)
        )


class WomanTest(AggregationScriptTestBase):
    always_include_columns = {'awc_id', 'village_id', 'person_case_id'}

    def test_agg_woman_table(self):
        self._load_and_compare_data(
            Woman,
            os.path.join(OUTPUT_PATH, 'woman.csv'),
            sort_key=['awc_id', 'village_id', 'person_case_id']
        )


class ChildTest(AggregationScriptTestBase):
    always_include_columns = {'awc_id', 'village_id', 'person_case_id'}

    def test_agg_child_table(self):
        self._load_and_compare_data(
            Child,
            os.path.join(OUTPUT_PATH, 'child.csv'),
            sort_key=['awc_id', 'village_id', 'person_case_id']
        )


class CcsRecordTest(AggregationScriptTestBase):
    always_include_columns = {'awc_id', 'village_id', 'ccs_record_case_id'}

    def test_agg_ccs_record_table(self):
        self._load_and_compare_data(
            CcsRecord,
            os.path.join(OUTPUT_PATH, 'ccs_record.csv'),
            sort_key=['awc_id', 'village_id', 'ccs_record_case_id']
        )


class AggAwcTest(AggregationScriptTestBase):
    always_include_columns = {'awc_id'}

    def test_agg_awc_table(self):
        self._load_and_compare_data(
            AggAwc,
            os.path.join(OUTPUT_PATH, 'agg_awc.csv'),
            sort_key=['awc_id']
        )


class AggVillageTest(AggregationScriptTestBase):
    always_include_columns = {'village_id'}

    def test_agg_village_table(self):
        self._load_and_compare_data(
            AggVillage,
            os.path.join(OUTPUT_PATH, 'agg_village.csv'),
            sort_key=['village_id']
        )
