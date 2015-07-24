from collections import namedtuple
from datetime import datetime
from casexml.apps.case.mock import CaseBlock as MockCaseBlock, CaseBlockError
from casexml.apps.case.xml import V2
from corehq.apps.app_manager.xform import CaseBlock as XFormCaseBlock
from django.test import SimpleTestCase
from xml.etree import ElementTree


class ExtCaseTests(SimpleTestCase):

    def test_ext_case_sets_relationship(self):
        """
        Adding an extension case should set index relationship to "extension"
        """
        self.skipTest('Not implemented')

    def test_ext_case_cascade_close(self):
        """
        An extension case should be closed when its host case is closed
        """
        self.skipTest('Not implemented')

    def test_ext_case_owner(self):
        """
        An extension case owner should be its host case owner
        """
        self.skipTest('Not implemented')


class ExtCasePropertiesTests(SimpleTestCase):

    def test_ext_case_read_host_properties(self):
        """
        Properties of a host case should be available in a extension case
        """
        self.skipTest('Not implemented')

    def test_host_case_read_ext_properties(self):
        """
        Properties of a extension case should be available in a host case
        """
        self.skipTest('Not implemented')

    def test_ext_case_write_host_properties(self):
        """
        A extension case should be available to save host case properties
        """
        self.skipTest('Not implemented')

    def test_host_case_write_ext_properties(self):
        """
        A host case should be available to save extension case properties
        """
        self.skipTest('Not implemented')


class MockCaseBlockIndexTests(SimpleTestCase):

    IndexAttrs = namedtuple('IndexAttrs', ['case_type', 'case_id', 'relationship'])
    now = datetime(year=2015, month=7, day=24)

    def test_mock_case_block_index_supports_relationship(self):
        """
        mock.CaseBlock index should allow the relationship to be set
        """
        case_block = MockCaseBlock(
            case_id='abcdef',
            case_type='at_risk',
            date_modified=self.now,
            index={
                'host_case': self.IndexAttrs(case_type='newborn', case_id='123456', relationship='extension')
            },
            version=V2,
        )

        self.assertEqual(
            ElementTree.tostring(case_block.as_xml()),
            '<case case_id="abcdef" date_modified="2015-07-24" xmlns="http://commcarehq.org/case/transaction/v2">'
                '<update>'
                    '<case_type>at_risk</case_type>'
                '</update>'
                '<index>'
                    '<host_case case_type="newborn" relationship="extension">123456</host_case>'
                '</index>'
            '</case>'
        )

    def test_mock_case_block_index_default_relationship(self):
        """
        mock.CaseBlock index relationship should default to "child"
        """
        case_block = MockCaseBlock(
            case_id='123456',
            case_type='newborn',
            date_modified=self.now,
            index={
                'parent': ('mother', '789abc')
            },
            version=V2,
        )

        self.assertEqual(
            ElementTree.tostring(case_block.as_xml()),
            '<case case_id="123456" date_modified="2015-07-24" xmlns="http://commcarehq.org/case/transaction/v2">'
                '<update>'
                    '<case_type>newborn</case_type>'
                '</update>'
                '<index>'
                    '<parent case_type="mother" relationship="child">789abc</parent>'
                '</index>'
            '</case>'
        )

    def test_mock_case_block_index_valid_relationship(self):
        """
        mock.CaseBlock index relationship should only allow valid values
        """
        with self.assertRaisesRegex(CaseBlockError,
                                    'Valid values for an index relationship are "child" and "extension"'):
            MockCaseBlock(
                case_id='abcdef',
                case_type='at_risk',
                date_modified=self.now,
                index={
                    'host_case': self.IndexAttrs(case_type='newborn', case_id='123456', relationship='parent')
                },
                version=V2,
            )


class XFormCaseBlockIndexTest(SimpleTestCase):

    def test_xform_case_block_index_supports_relationship(self):
        """
        XForm CaseBlock index should allow the relationship to be set
        """
        # case_block = XFormCaseBlock(xform, node_path)
        self.skipTest('Not implemented')

    def test_xform_case_block_index_default_relationship(self):
        """
        XForm CaseBlock index relationship should default to "child"
        """
        self.skipTest('Not implemented')

    def test_xform_case_block_index_valid_relationship(self):
        """
        XForm CaseBlock index relationship should only allow valid values
        """
        self.skipTest('Not implemented')


class OpenSubCaseActionTests(SimpleTestCase):

    def test_open_subcase_action_supports_relationship(self):
        """
        OpenSubCaseAction should allow relationship to be set
        """
        self.skipTest('Not implemented')

    def test_open_subcase_action_default_relationship(self):
        """
        OpenSubCaseAction relationship should default to "child"
        """
        self.skipTest('Not implemented')

    def test_open_subcase_action_valid_relationship(self):
        """
        OpenSubCaseAction relationship should only allow valid values
        """
        self.skipTest('Not implemented')


class AdvancedActionTests(SimpleTestCase):

    def test_advanced_action_supports_relationship(self):
        """
        AdvancedAction should allow relationship to be set
        """
        self.skipTest('Not implemented')

    def test_advanced_action_default_relationship(self):
        """
        AdvancedAction relationship should default to "child"
        """
        self.skipTest('Not implemented')

    def test_advanced_action_valid_relationship(self):
        """
        AdvancedAction relationship should only allow valid values
        """
        self.skipTest('Not implemented')
