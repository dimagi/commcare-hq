from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

from django.test import SimpleTestCase
from mock import patch, Mock

from corehq.apps.app_manager.tests.util import TestXmlMixin
from custom.icds.messaging.indicators import LSAggregatePerformanceIndicator
from custom.icds.const import (
    CHILDREN_WEIGHED_REPORT_ID,
    DAYS_AWC_OPEN_REPORT_ID,
    HOME_VISIT_REPORT_ID,
    THR_REPORT_ID,
)


class PropertyMock(Mock):
    def __get__(self, instance, owner):
        return self()


class TestLSAggregatePerformanceIndicator(SimpleTestCase, TestXmlMixin):
    file_path = ('../../../..', 'custom/icds/tests/data/fixtures')

    @patch.object(LSAggregatePerformanceIndicator, 'visits_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'thr_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'weighed_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'days_open_fixture', new_callable=PropertyMock)
    def test_report_parsing(self, days_open, weighed, thr, visits):
        days_open.return_value = ET.fromstring(self.get_xml('days_open_fixture'))
        weighed.return_value = ET.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = ET.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = ET.fromstring(self.get_xml('visit_fixture'))
        indicator = LSAggregatePerformanceIndicator('domain', 'user')
        message = indicator.get_messages()[0]
        self.assertTrue('Home Visits - 269/65' in message)
        self.assertTrue('THR Distribution - 19 / 34' in message)
        self.assertTrue('Number of children weighed - 33 / 33' in message)
        self.assertTrue('Days AWC open -  117/25' in message)
