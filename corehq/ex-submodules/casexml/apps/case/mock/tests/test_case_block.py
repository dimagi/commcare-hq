from datetime import datetime

import six
from django.test import SimpleTestCase
from xml.etree import cElementTree as ElementTree
from casexml.apps.case.mock import CaseBlock, CaseBlockError
from corehq.tests.util.xml import assert_xml_equal


class CaseBlockTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(CaseBlockTest, cls).setUpClass()
        cls.NOW = datetime(year=2012, month=1, day=24)
        cls.FIVE_DAYS_FROM_NOW = datetime(year=2012, month=1, day=29)
        cls.CASE_ID = 'test-case-id'

    def test_basic(self):
        actual = ElementTree.tostring(CaseBlock(
            case_id=self.CASE_ID,
            date_opened=self.NOW,
            date_modified=self.NOW,
        ).as_xml(), encoding='utf-8').decode('utf-8')
        expected = (
            '<case case_id="test-case-id" date_modified="2012-01-24T00:00:00.000000Z" '
            'xmlns="http://commcarehq.org/case/transaction/v2">'
            '<update><date_opened>2012-01-24T00:00:00.000000Z</date_opened></update>'
            '</case>'
        )
        assert_xml_equal(actual, expected)

    def test_does_not_let_you_specify_a_keyword_twice(self):
        """Doesn't let you specify a keyword twice (here 'case_name')"""
        with self.assertRaises(CaseBlockError) as context:
            CaseBlock(
                case_id=self.CASE_ID,
                case_name='Johnny',
                update={'case_name': 'Johnny'},
            ).as_xml()
        self.assertEqual(six.text_type(context.exception), "Key 'case_name' specified twice")

    def test_let_you_specify_system_props_for_create_via_updates(self):
        actual = ElementTree.tostring(CaseBlock(
            case_id=self.CASE_ID,
            create=True,
            update={'case_name': 'Johnny'},
            date_modified=self.NOW,
        ).as_xml(), encoding='utf-8').decode('utf-8')
        expected = (
            '<case case_id="test-case-id" date_modified="2012-01-24T00:00:00.000000Z" '
            'xmlns="http://commcarehq.org/case/transaction/v2">'
            '<create><case_type /><case_name /><owner_id /></create>'
            '<update><case_name>Johnny</case_name></update>'
            '</case>'
        )
        self.assertEqual(actual, expected)

    def test_buggy_behavior(self):
        """The following is a BUG; should fail!! Should fix and change tests"""
        expected = ElementTree.tostring(CaseBlock(
            case_id=self.CASE_ID,
            date_opened=self.NOW,
            date_modified=self.NOW,
            update={
                'date_opened': self.FIVE_DAYS_FROM_NOW,
            },
        ).as_xml(), encoding='utf-8').decode('utf-8')
        actual = (
            '<case case_id="test-case-id" date_modified="2012-01-24T00:00:00.000000Z" '
            'xmlns="http://commcarehq.org/case/transaction/v2">'
            '<update><date_opened>2012-01-24T00:00:00.000000Z</date_opened></update>'
            '</case>'
        )
        self.assertEqual(actual, expected)

    def test_owner_id_is_none(self):
        case_block = CaseBlock(
            case_id=self.CASE_ID,
            owner_id=None,
        )
        self.assertEqual(case_block.owner_id, ...)

    def test_date_opened_default(self):
        case_block = CaseBlock(
            case_id=self.CASE_ID,
        )
        self.assertEqual(case_block.date_opened, ...)

    def test_date_opened_given(self):
        day_one = datetime(year=1970, month=1, day=1)
        case_block = CaseBlock(
            case_id=self.CASE_ID,
            date_opened=day_one,
        )
        self.assertEqual(case_block.date_opened, day_one)

    def test_date_opened_deprecated_given(self):
        day_one = datetime(year=1970, month=1, day=1)
        case_block = CaseBlock(
            case_id=self.CASE_ID,
            date_opened=day_one,
            create=True,
            date_opened_deprecated_behavior=True,
        )
        self.assertEqual(case_block.date_opened, day_one)

    def test_date_opened_deprecated_now(self):
        now = datetime.utcnow().date()
        case_block = CaseBlock(
            case_id=self.CASE_ID,
            create=True,
            date_opened_deprecated_behavior=True,
        )
        self.assertEqual(case_block.date_opened, now)
