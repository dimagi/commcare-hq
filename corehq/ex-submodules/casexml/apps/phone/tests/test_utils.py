from __future__ import absolute_import

from __future__ import unicode_literals
from datetime import datetime

from django.test import SimpleTestCase, override_settings

import casexml.apps.phone.utils as mod
from casexml.apps.case.mock import CaseStructure
from casexml.apps.case.tests.util import delete_all_cases, delete_all_ledgers, delete_all_xforms
from casexml.apps.phone.tests.test_sync_mode import BaseSyncTest
from casexml.apps.stock.mock import Balance, Entry, Transfer
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.test_utils import flag_enabled


class TestUtils(SimpleTestCase):

    def test_get_cached_items_with_count_no_count(self):
        XML = b'<fixture />'
        xml, num = mod.get_cached_items_with_count(XML)
        self.assertEqual(xml, XML)
        self.assertEqual(num, 1)

    def test_get_cached_items_with_count(self):
        XML = b'<!--items=42--><fixture>...</fixture>'
        xml, num = mod.get_cached_items_with_count(XML)
        self.assertEqual(xml, b'<fixture>...</fixture>')
        self.assertEqual(num, 42)

    def test_get_cached_items_with_count_bad_format(self):
        XML = b'<!--items=2JUNK--><fixture>...</fixture>'
        xml, num = mod.get_cached_items_with_count(XML)
        self.assertEqual(xml, XML)
        self.assertEqual(num, 1)


@flag_enabled('NON_COMMTRACK_LEDGERS')
@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class MockDeviceLedgersTest(BaseSyncTest, TestXmlMixin):
    def setUp(self):
        super(MockDeviceLedgersTest, self).setUp()
        self.accessor = CaseAccessors(self.project.name)
        self._create_ledgers()

    def tearDown(self):
        delete_all_ledgers()
        delete_all_cases()
        delete_all_xforms()
        super(MockDeviceLedgersTest, self).tearDown()

    def _create_ledgers(self):
        case_type = 'case'

        case1 = CaseStructure(
            case_id='case1',
            attrs={'create': True, 'case_type': case_type},
        )
        case2 = CaseStructure(
            case_id='case2',
            attrs={'create': True, 'case_type': case_type},
        )
        entry = Entry(id='icecream', quantity=4)
        self.balance = Balance(
            entity_id=case1.case_id,
            date=datetime(2017, 11, 21, 0, 0, 0, 0),
            section_id='test',
            entry=entry,
        )  # start case1 off with 4 items
        self.transfer = Transfer(
            src=case1.case_id,
            dest=case2.case_id,
            date=datetime(2017, 11, 21, 0, 0, 0, 0),
            type='stuff',
            section_id='test',
            entry=entry,
        )  # transfer all 4 items to case 2
        self.device.post_changes([case1, case2])
        transfer_form = self.device.post_changes([self.balance, self.transfer])
        self.transaction_date = transfer_form.received_on

    def test_ledgers(self):
        ledgers = self.device.restore().ledgers
        case1_node = """
            <partial>
              <ns0:balance xmlns:ns0="http://commcarehq.org/ledger/v1"
                           date="{date}"
                           entity-id="case1"
                           section-id="test">
              <ns0:entry id="icecream" quantity="0"/></ns0:balance>
            </partial>
        """.format(date=self.transaction_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ'))
        case2_node = """
            <partial>
              <ns0:balance xmlns:ns0="http://commcarehq.org/ledger/v1"
                           date="{date}"
                           entity-id="case2"
                           section-id="test">
              <ns0:entry id="icecream" quantity="4"/></ns0:balance>
            </partial>
        """.format(date=self.transaction_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ'))
        self.assertXmlPartialEqual(case1_node, ledgers['case1'][0].serialize(), '.')
        self.assertXmlPartialEqual(case2_node, ledgers['case2'][0].serialize(), '.')
