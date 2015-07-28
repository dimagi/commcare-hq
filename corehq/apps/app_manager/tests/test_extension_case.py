from collections import namedtuple
from datetime import datetime
import re
from casexml.apps.case.mock import CaseBlock as MockCaseBlock, CaseBlockError
from casexml.apps.case.xml import V2
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.models import Application, Module, UpdateCaseAction
from corehq.apps.app_manager.tests import TestFileMixin
from corehq.apps.app_manager.xform import CaseBlock as XFormCaseBlock
from django.test import SimpleTestCase
from xml.etree import ElementTree
from mock import patch


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


class ExtCasePropertiesTests(SimpleTestCase, TestFileMixin):
    file_path = 'data', 'extension_case'

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()

        self.app = Application.new_app('domain', 'New App', APP_V2)
        self.app.version = 3
        self.fish_module = self.app.add_module(Module.new_module('Fish Module', lang='en'))
        self.fish_module.case_type = 'fish'
        self.fish_form = self.app.new_form(0, 'New Form', lang='en')
        self.fish_form.source = self.get_xml('original')

        self.freshwater_module = self.app.add_module(Module.new_module('Freshwater Module', lang='en'))
        self.freshwater_module.case_type = 'freshwater'
        self.freshwater_form = self.app.new_form(0, 'New Form', lang='en')
        self.freshwater_form.source = self.get_xml('original')

        self.aquarium_module = self.app.add_module(Module.new_module('Aquarium Module', lang='en'))
        self.aquarium_module.case_type = 'aquarium'

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def test_ext_case_preload_host_case(self):
        """
        Properties of a host case should be available in a extension case
        """
        self.skipTest('Not implemented')

    def test_ext_case_update_host_case(self):
        """
        A extension case should be able to save host case properties
        """
        self.freshwater_form.requires = 'case'
        self.freshwater_form.actions.update_case = UpdateCaseAction(update={
            'question1': '/data/question1',
            'hostcase/question1': '/data/question1',
        })
        self.freshwater_form.actions.update_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('update_host_case'), self.freshwater_form.render_xform())

    def test_host_case_preload_ext_case(self):
        """
        Properties of a extension case should be available in a host case
        """
        self.skipTest('Not implemented')

    def test_host_case_update_ext_case(self):
        """
        A host case should be able to save extension case properties
        """
        self.fish_form.requires = 'case'
        self.fish_form.actions.update_case = UpdateCaseAction(update={
            'question1': '/data/question1',
            'ext/freshwater/question1': '/data/question1',
            'ext/aquarium/question1': '/data/question1',
        })
        self.fish_form.actions.update_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('update_host_case'), self.form.render_xform())


class ExtCasePropertiesTestsAdvanced(SimpleTestCase, TestFileMixin):

    # def test_ext_case_preload_host_case(self):

    def test_ext_case_update_host_case(self):
        """
        A extension case should be able to save host case properties in an advanced module
        """
        self.skipTest('Not implemented')
        # FormPreparationV2Test.test_update_parent_case(self):
        # self.form.actions.load_update_cases.append(LoadUpdateAction(
        #     case_type=self.module.case_type,
        #     case_tag='load_1',
        #     case_properties={'question1': '/data/question1', 'parent/question1': '/data/question1'}
        # ))
        # self.assertXmlEqual(self.get_xml('update_parent_case'), self.form.render_xform())

    # def test_host_case_preload_ext_case(self):

    # def test_host_case_update_ext_case(self):


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
                'hostcase': self.IndexAttrs(case_type='newborn', case_id='123456', relationship='extension')
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
                    '<hostcase case_type="newborn" relationship="extension">123456</hostcase>'
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
                    'hostcase': self.IndexAttrs(case_type='newborn', case_id='123456', relationship='parent')
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
