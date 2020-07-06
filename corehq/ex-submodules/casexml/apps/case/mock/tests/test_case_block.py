from datetime import datetime

import six
from django.test import SimpleTestCase
from xml.etree import cElementTree as ElementTree
from casexml.apps.case.mock import CaseBlock, CaseBlockError


class CaseBlockTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(CaseBlockTest, cls).setUpClass()
        cls.NOW = datetime(year=2012, month=1, day=24)
        cls.FIVE_DAYS_FROM_NOW = datetime(year=2012, month=1, day=29)
        cls.CASE_ID = 'test-case-id'

    def test_basic(self):
        actual = ElementTree.tostring(CaseBlock.deprecated_init(
            case_id=self.CASE_ID,
            date_opened=self.NOW,
            date_modified=self.NOW,
        ).as_xml()).decode('utf-8')
        expected = (
            '<case case_id="test-case-id" date_modified="2012-01-24T00:00:00.000000Z" '
            'xmlns="http://commcarehq.org/case/transaction/v2">'
            '<update><date_opened>2012-01-24T00:00:00.000000Z</date_opened></update>'
            '</case>'
        )
        self.assertEqual(actual, expected)

    def test_does_not_let_you_specify_a_keyword_twice(self):
        """Doesn't let you specify a keyword twice (here 'case_name')"""
        with self.assertRaises(CaseBlockError) as context:
            CaseBlock.deprecated_init(
                case_id=self.CASE_ID,
                case_name='Johnny',
                update={'case_name': 'Johnny'},
            ).as_xml()
        self.assertEqual(six.text_type(context.exception), "Key 'case_name' specified twice")

    def test_buggy_behavior(self):
        """The following is a BUG; should fail!! Should fix and change tests"""
        expected = ElementTree.tostring(CaseBlock.deprecated_init(
            case_id=self.CASE_ID,
            date_opened=self.NOW,
            date_modified=self.NOW,
            update={
                'date_opened': self.FIVE_DAYS_FROM_NOW,
            },
        ).as_xml()).decode('utf-8')
        actual = (
            '<case case_id="test-case-id" date_modified="2012-01-24T00:00:00.000000Z" '
            'xmlns="http://commcarehq.org/case/transaction/v2">'
            '<update><date_opened>2012-01-24T00:00:00.000000Z</date_opened></update>'
            '</case>'
        )
        self.assertEqual(actual, expected)
