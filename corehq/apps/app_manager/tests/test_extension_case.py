from django.test import SimpleTestCase

from couchdbkit import BadValueError
from mock import patch

from corehq.apps.app_manager.exceptions import CaseError
from corehq.apps.app_manager.models import (
    AdvancedModule,
    AdvancedOpenCaseAction,
    Application,
    CaseIndex,
    FormActionCondition,
    LoadUpdateAction,
    Module,
    OpenSubCaseAction,
    PreloadAction,
    UpdateCaseAction,
)
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.xform import (
    XFormCaseBlock,
    XForm,
    _make_elem,
    autoset_owner_id_for_advanced_action,
)
from corehq.apps.app_manager.xpath import session_var


class ExtCasePropertiesTests(SimpleTestCase, TestXmlMixin):
    file_path = 'data', 'extension_case'

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()

        self.app = Application.new_app('domain', 'New App')
        self.app.version = 3
        self.fish_module = self.app.add_module(Module.new_module('Fish Module', lang='en'))
        self.fish_module.case_type = 'fish'
        self.fish_form = self.app.new_form(0, 'New Form', lang='en')
        self.fish_form.source = self.get_xml('original').decode('utf-8')

        self.freshwater_module = self.app.add_module(Module.new_module('Freshwater Module', lang='en'))
        self.freshwater_module.case_type = 'freshwater'
        self.freshwater_form = self.app.new_form(0, 'New Form', lang='en')
        self.freshwater_form.source = self.get_xml('original').decode('utf-8')

        self.aquarium_module = self.app.add_module(Module.new_module('Aquarium Module', lang='en'))
        self.aquarium_module.case_type = 'aquarium'

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def test_ext_case_preload_host_case(self):
        """
        Properties of a host case should be available in a extension case
        """
        self.freshwater_form.requires = 'case'
        self.freshwater_form.actions.case_preload = PreloadAction(preload={
            '/data/question1': 'question1',
            '/data/question2': 'host/question2',
        })
        self.freshwater_form.actions.update_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('preload_host_case'), self.freshwater_form.render_xform())

    def test_ext_case_update_host_case(self):
        """
        A extension case should be able to save host case properties
        """
        self.freshwater_form.requires = 'case'
        self.freshwater_form.actions.update_case = UpdateCaseAction(update={
            'question1': '/data/question1',
            'host/question1': '/data/question1',
        })
        self.freshwater_form.actions.update_case.condition.type = 'always'
        self.assertXmlEqual(self.get_xml('update_host_case'), self.freshwater_form.render_xform())

    def test_host_case_preload_ext_cases(self):
        """
        Properties of one or more extension cases should be available in a host case
        """
        self.skipTest('TODO: Write this test')

    def test_host_case_update_ext_cases(self):
        """
        A host case should be able to save properties of one or more extension cases
        """
        self.skipTest('TODO: Write this test')


class ExtCasePropertiesAdvancedTests(SimpleTestCase, TestXmlMixin):
    file_path = 'data', 'extension_case'

    def setUp(self):
        self.app = Application.new_app('domain', 'New App')
        self.app.version = 3
        self.module = self.app.add_module(AdvancedModule.new_module('New Module', lang='en'))
        self.module.case_type = 'test_case_type'
        self.form = self.module.new_form("Untitled Form", "en", self.get_xml('original').decode('utf-8'))

        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def test_ext_case_preload_host_case(self):
        """
        A extension case should be able to preload host case properties in an advanced module
        """
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_1',
            preload={
                '/data/question1': 'question1',
                '/data/question2': 'host/question2'
            },
        ))
        self.assertXmlEqual(self.get_xml('preload_host_case_adv'), self.form.render_xform())

    def test_ext_case_update_host_case(self):
        """
        A extension case should be able to save host case properties in an advanced module
        """
        self.form.actions.load_update_cases.append(LoadUpdateAction(
            case_type=self.module.case_type,
            case_tag='load_1',
            case_properties={
                'question1': '/data/question1',
                'host/question1': '/data/question1'
            },
        ))
        self.assertXmlEqual(self.get_xml('update_host_case_adv'), self.form.render_xform())

    def test_host_case_preload_ext_case(self):
        self.skipTest('TODO: Write this test')

    def test_host_case_update_ext_case(self):
        self.skipTest('TODO: Write this test')


class CaseBlockIndexRelationshipTest(SimpleTestCase, TestXmlMixin):
    file_path = 'data', 'extension_case'

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()
        self.is_usercase_in_use_mock.return_value = True

        self.app = Application.new_app('domain', 'New App')
        self.module = self.app.add_module(AdvancedModule.new_module('Fish Module', None))
        self.module.case_type = 'fish'
        self.form = self.module.new_form('Form', 'en', self.get_xml('original').decode('utf-8'))
        self.other_module = self.app.add_module(AdvancedModule.new_module('Freshwater Module', lang='en'))
        self.other_module.case_type = 'freshwater'
        self.other_form = self.module.new_form('Other Form', 'en', self.get_xml('original').decode('utf-8'))
        self.case_index = CaseIndex(
            reference_id='host',
            relationship='extension',
        )
        self.subcase = AdvancedOpenCaseAction(
            case_tag='open_freshwater_0',
            case_type='freshwater',
            case_name='Wanda',
            name_path='/data/question1',
            open_condition=FormActionCondition(type='always'),
            case_properties={'name': '/data/question1'},
            case_indices=[self.case_index],
        )
        self.form.actions.open_cases.append(self.subcase)
        self.xform = XForm(self.get_xml('original'))
        path = 'subcase_0/'
        self.subcase_block = XFormCaseBlock(self.xform, path)

    def add_subcase_block(self):

        parent_node = self.xform.data_node
        action = next(self.form.actions.get_open_actions())
        case_id = session_var(action.case_session_var)
        subcase_node = _make_elem('{x}subcase_0')
        parent_node.append(subcase_node)
        subcase_node.insert(0, self.subcase_block.elem)
        self.subcase_block.add_create_block(
            relevance=self.xform.action_relevance(action.open_condition),
            case_name=self.subcase.case_name,
            case_type=self.subcase.case_type,
            delay_case_id=bool(self.subcase.repeat_context),
            autoset_owner_id=autoset_owner_id_for_advanced_action(action),
            has_case_sharing=self.form.get_app().case_sharing,
            case_id=case_id
        )
        self.subcase_block.add_case_updates(self.subcase.case_properties)

    def test_xform_case_block_index_supports_relationship(self):
        """
        CaseBlock index should allow the relationship to be set
        """
        self.add_subcase_block()
        self.subcase_block.add_index_ref(
            'host',
            self.form.get_case_type(),
            self.xform.resolve_path("case/@case_id"),
            self.subcase.case_indices[0].relationship,
        )
        self.assertXmlEqual(self.get_xml('open_subcase'), str(self.xform))

    def test_xform_case_block_index_supports_dynamic_relationship(self):
        self.subcase.case_indices = [CaseIndex(
            tag='open_freshwater_0',
            reference_id='node',
            relationship='question',
            relationship_question='/data/question2',
        )]
        self.assertXmlEqual(self.get_xml('case_index_relationship_question'), self.form.render_xform())

    def test_xform_case_block_index_default_relationship(self):
        """
        CaseBlock index relationship should default to "child"
        """
        child = CaseIndex(
            reference_id='host',
            relationship='child',
        )
        self.subcase.case_indices = [child]
        self.add_subcase_block()
        self.subcase_block.add_index_ref(
            'host',
            self.form.get_case_type(),
            self.xform.resolve_path("case/@case_id"),
        )
        self.assertXmlEqual(self.get_xml('open_subcase_child'), str(self.xform))

    def test_xform_case_block_index_valid_relationship(self):
        """
        CaseBlock index relationship should only allow valid values
        """
        with self.assertRaisesRegex(CaseError,
                                     'Valid values for an index relationship are'):
            self.subcase_block.add_index_ref(
                'host',
                self.form.get_case_type(),
                self.xform.resolve_path("case/@case_id"),
                'cousin',
            )


class ExtensionCasesCreateOwnerID(SimpleTestCase):

    def test_advanced_xform_autoset_owner_id(self):
        """
            Owner id should be automatically set if there are any non-extension indices.
            It should never be set if there are any dynamically-specified indices.
        """

        def _test_relationships(relationships, expected):
            advanced_open_action = AdvancedOpenCaseAction.wrap({'case_indices': [{
                'tag': 'tag{}'.format(i),
                'reference_id': 'case',
                'relationship': r,
            } for i, r in enumerate(relationships)]})
            self.assertEqual(autoset_owner_id_for_advanced_action(advanced_open_action), expected)

        # Only extensions
        _test_relationships(['extension', 'extension'], False)

        # Extension and children
        _test_relationships(['extension', 'child'], True)

        # Dynamically-determined relationship
        _test_relationships(['extension', 'question'], False)
        _test_relationships(['child', 'question'], False)

        # No indices
        _test_relationships([], True)

    def test_advanced_xform_create_owner_id_explicitly_set(self):
        """When owner_id is explicitly set, don't autoset"""
        advanced_open_action = AdvancedOpenCaseAction.wrap({
            'case_properties': {'owner_id': 'owner'},
            'case_indices': [
                {
                    'tag': 'mother',
                    'reference_id': 'case',
                    'relationship': 'child'
                },
            ]
        })
        self.assertFalse(autoset_owner_id_for_advanced_action(advanced_open_action))

        advanced_open_action = AdvancedOpenCaseAction.wrap({
            'case_properties': {'owner_id': 'owner'},
            'case_indices': [
                {
                    'tag': 'mother',
                    'reference_id': 'case',
                    'relationship': 'extension'
                },
            ]
        })
        self.assertFalse(autoset_owner_id_for_advanced_action(advanced_open_action))

        advanced_open_action = AdvancedOpenCaseAction.wrap({
            'case_properties': {'owner_id': 'owner'},
        })
        self.assertFalse(autoset_owner_id_for_advanced_action(advanced_open_action))

        advanced_open_action = AdvancedOpenCaseAction()
        self.assertTrue(autoset_owner_id_for_advanced_action(advanced_open_action))


class OpenSubCaseActionTests(SimpleTestCase):

    def test_open_subcase_action_supports_relationship(self):
        """
        OpenSubCaseAction should allow relationship to be set
        """
        action = OpenSubCaseAction(case_type='mother', case_name='Eva', relationship='extension')
        self.assertEqual(action.relationship, 'extension')

    def test_open_subcase_action_default_relationship(self):
        """
        OpenSubCaseAction relationship should default to "child"
        """
        action = OpenSubCaseAction(case_type='mother', case_name='Eva')
        self.assertEqual(action.relationship, 'child')

    def test_open_subcase_action_valid_relationship(self):
        """
        OpenSubCaseAction relationship should only allow valid values
        """
        OpenSubCaseAction(case_type='mother', case_name='Eva', relationship='child')
        OpenSubCaseAction(case_type='mother', case_name='Eva', relationship='extension')
        with self.assertRaises(BadValueError):
            OpenSubCaseAction(case_type='mother', case_name='Eva', relationship='parent')
        with self.assertRaises(BadValueError):
            OpenSubCaseAction(case_type='mother', case_name='Eva', relationship='host')
        with self.assertRaises(BadValueError):
            OpenSubCaseAction(case_type='mother', case_name='Eva', relationship='primary')
        with self.assertRaises(BadValueError):
            OpenSubCaseAction(case_type='mother', case_name='Eva', relationship='replica')
        with self.assertRaises(BadValueError):
            OpenSubCaseAction(case_type='mother', case_name='Eva', relationship='cousin')


class CaseIndexTests(SimpleTestCase):

    def test_case_index_support_relationship(self):
        """
        CaseIndex should allow relationship to be set
        """
        case_index = CaseIndex(tag='mother', relationship='extension')
        self.assertEqual(case_index.relationship, 'extension')

    def test_case_index_default_relationship(self):
        """
        CaseIndex relationship should default to "child"
        """
        case_index = CaseIndex(tag='mother')
        self.assertEqual(case_index.relationship, 'child')

    def test_case_index_valid_relationship(self):
        """
        CaseIndex relationship should only allow valid values
        """
        CaseIndex(tag='mother', relationship='child')
        CaseIndex(tag='mother', relationship='extension')
        CaseIndex(tag='mother', relationship='question')
        with self.assertRaises(BadValueError):
            CaseIndex(tag='mother', relationship='parent')
        with self.assertRaises(BadValueError):
            CaseIndex(tag='mother', relationship='host')
        with self.assertRaises(BadValueError):
            CaseIndex(tag='mother', relationship='primary')
        with self.assertRaises(BadValueError):
            CaseIndex(tag='mother', relationship='replica')
        with self.assertRaises(BadValueError):
            CaseIndex(tag='mother', relationship='cousin')


class AdvancedOpenCaseActionMigrationTests(SimpleTestCase):

    def test_parent_tag(self):
        """
        AdvancedOpenCaseAction migration should create a CaseIndex if a parent tag is given
        """
        action = AdvancedOpenCaseAction.wrap({
            'case_type': 'spam',
            'case_tag': 'ham',
            'parent_tag': 'eggs',
        })
        self.assertEqual(action.case_indices[0].tag, 'eggs')

    def test_defaults(self):
        """
        AdvancedOpenCaseAction migration should create a CaseIndex with property defaults
        """
        action = AdvancedOpenCaseAction.wrap({
            'case_type': 'spam',
            'case_tag': 'ham',
            'parent_tag': 'eggs',
        })
        self.assertEqual(action.case_indices[0].reference_id, 'parent')
        self.assertEqual(action.case_indices[0].relationship, 'child')

    def test_properties(self):
        """
        AdvancedOpenCaseAction migration should create a CaseIndex with given properties
        """
        action = AdvancedOpenCaseAction.wrap({
            'case_type': 'spam',
            'case_tag': 'ham',
            'parent_tag': 'eggs',
            'parent_reference_id': 'spam',
            'relationship': 'extension',
        })
        self.assertEqual(action.case_indices[0].tag, 'eggs')
        self.assertEqual(action.case_indices[0].reference_id, 'spam')
        self.assertEqual(action.case_indices[0].relationship, 'extension')

    def test_advanced_action_no_parent_tag(self):
        """
        AdvancedOpenCaseAction migration should not create a CaseIndex without parent_tag
        """
        action = AdvancedOpenCaseAction.wrap({
            'case_type': 'spam',
            'case_tag': 'ham',
            'parent_reference_id': 'spam',
            'relationship': 'extension',
        })
        self.assertEqual(len(action.case_indices), 0)


class LoadUpdateActionMigrationTests(SimpleTestCase):

    def test_parent_tag(self):
        """
        LoadUpdateAction migration should create a CaseIndex if a parent tag is given
        """
        action = LoadUpdateAction.wrap({
            'case_type': 'spam',
            'case_tag': 'ham',
            'parent_tag': 'eggs',
        })
        self.assertEqual(action.case_index.tag, 'eggs')

    def test_defaults(self):
        """
        LoadUpdateAction migration should create a CaseIndex with property defaults
        """
        action = LoadUpdateAction.wrap({
            'case_type': 'spam',
            'case_tag': 'ham',
            'parent_tag': 'eggs',
        })
        self.assertEqual(action.case_index.reference_id, 'parent')
        self.assertEqual(action.case_index.relationship, 'child')

    def test_properties(self):
        """
        LoadUpdateAction migration should create a CaseIndex with given properties
        """
        action = LoadUpdateAction.wrap({
            'case_type': 'spam',
            'case_tag': 'ham',
            'parent_tag': 'eggs',
            'parent_reference_id': 'spam',
            'relationship': 'extension',
        })
        self.assertEqual(action.case_index.tag, 'eggs')
        self.assertEqual(action.case_index.reference_id, 'spam')
        self.assertEqual(action.case_index.relationship, 'extension')

    def test_advanced_action_no_parent_tag(self):
        """
        LoadUpdateAction migration should not create a CaseIndex without parent_tag
        """
        action = LoadUpdateAction.wrap({
            'case_type': 'spam',
            'case_tag': 'ham',
            'parent_reference_id': 'spam',
            'relationship': 'extension',
        })
        self.assertFalse(bool(action.case_index.tag))
