from xml.etree import cElementTree as ElementTree

from django.test import SimpleTestCase

from casexml.apps.case.tests.util import check_xml_line_by_line

from corehq.apps.fixtures.models import (
    FieldList,
    FixtureDataItem,
    FixtureItemField,
    LookupTable,
    TypeField,
)
from corehq.apps.fixtures.fixturegenerators import item_lists
from corehq.apps.fixtures.utils import is_identifier_invalid


class FieldNameCleanTest(SimpleTestCase):
    """Makes sure that bad characters are properly escaped in the xml"""

    def setUp(self):
        self.domain = 'dirty-fields'

        self.data_type = LookupTable(
            domain=self.domain,
            tag='dirty_fields',
            description="Dirty Fields",
            fields=[
                TypeField(name="will/crash"),
                TypeField(name="space cadet"),
                TypeField(name="yes\\no"),
                TypeField(name="<with>"),
                TypeField(name="<crazy / combo><d")
            ],
            item_attributes=[],
        )

        self.data_item = FixtureDataItem(
            domain=self.domain,
            data_type_id=self.data_type._migration_couch_id,
            fields={
                "will/crash": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="yep",
                            properties={}
                        )
                    ]
                ),
                "space cadet": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="major tom",
                            properties={}
                        )
                    ]
                ),
                "yes\\no": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="no, duh",
                            properties={}
                        )
                    ]
                ),
                "<with>": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="so fail",
                            properties={}
                        )
                    ]
                ),
                "<crazy / combo><d": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="just why",
                            properties={}
                        )
                    ]
                ),
                "xmlbad": FieldList(
                    field_list=[
                        FixtureItemField(
                            field_value="badxml",
                            properties={}
                        )
                    ]
                )
            },
            item_attributes={},
        )

    def test_cleaner(self):
        item_dict = self.data_item.to_json()
        item_dict['_data_type'] = self.data_type
        check_xml_line_by_line(self, """
        <dirty_fields>
            <will_crash>yep</will_crash>
            <space_cadet>major tom</space_cadet>
            <yes_no>no, duh</yes_no>
            <_with_>so fail</_with_>
            <_crazy___combo__d>just why</_crazy___combo__d>
        </dirty_fields>
        """, ElementTree.tostring(item_lists.to_xml(item_dict), encoding='utf-8'))


class FieldNameValidationTest(SimpleTestCase):
    """Makes sure that the field name validator does what's expected.
    """

    def test_slash(self):
        bad_name = "will/crash"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_space(self):
        bad_name = "space cadet"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_xml(self):
        bad_name = "xml_and_more"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_backslash(self):
        bad_name = "space\\cadet"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_brackets(self):
        bad_name = "<space>"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_combo(self):
        bad_name = "<space>\\<dadgg sd"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_starts_with_number(self):
        bad_name = "0hello"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_punctuation(self):
        bad_name = "ﾉｲ丂 ﾑ ｲ尺ﾑｱ! \\_(ツ)_/¯"
        self.assertTrue(is_identifier_invalid(bad_name))

    def test_alphanumeric_nonascii(self):
        good_name = "província"
        self.assertFalse(is_identifier_invalid(good_name))

    def test_alphanumeric_unicode(self):
        good_name = "田纳西一二三"
        self.assertFalse(is_identifier_invalid(good_name))

    def test_good(self):
        good_name = "fooxmlbar0123"
        self.assertFalse(is_identifier_invalid(good_name))
