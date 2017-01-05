import os
from mock import patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.export.models.new import MAIN_TABLE, \
    PathNode, _question_path_to_path_nodes

from corehq.util.context_managers import drop_connected_signals
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.models import (
    XForm,
    Application,
    OpenSubCaseAction,
    AdvancedModule,
    AdvancedOpenCaseAction,
)
from corehq.apps.app_manager.signals import app_post_save
from corehq.apps.export.dbaccessors import delete_all_export_data_schemas, delete_all_inferred_schemas
from corehq.apps.export.tasks import add_inferred_export_properties
from corehq.apps.export.models import (
    FormExportDataSchema,
    CaseExportDataSchema,
    ExportDataSchema,
    InferredExportGroupSchema,
    InferredSchema,
    ExportGroupSchema,
    ExportItem,
    LabelItem,
    PARENT_CASE_TABLE,
)
from corehq.apps.export.const import (
    KNOWN_CASE_PROPERTIES,
    PROPERTY_TAG_UPDATE,
    FORM_DATA_SCHEMA_VERSION,
    CASE_ATTRIBUTES,
    CASE_CREATE_ELEMENTS,
)


class TestFormExportDataSchema(SimpleTestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)
    app_id = '1234'

    def test_basic_xform_parsing(self):
        form_xml = self.get_xml('basic_form')

        schema = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            [],
            ['en'],
            self.app_id,
            1
        )

        self.assertEqual(len(schema.group_schemas), 1)

        group_schema = schema.group_schemas[0]

        self.assertEqual(len(group_schema.items), 2)

        form_items = filter(lambda item: item.tag is None, group_schema.items)
        self.assertEqual(form_items[0].path, [PathNode(name='form'), PathNode(name='question1')])
        self.assertEqual(form_items[1].path, [PathNode(name='form'), PathNode(name='question2')])

    def test_labels_in_xform(self):
        form_xml = self.get_xml('form_with_labels')

        schema = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            [],
            ['en'],
            self.app_id,
            1
        )

        self.assertEqual(len(schema.group_schemas), 1)

        group_schema = schema.group_schemas[0]

        self.assertEqual(len(group_schema.items), 1)
        self.assertEqual(group_schema.items[0].path, [PathNode(name='form'), PathNode(name='label')])
        self.assertIsInstance(group_schema.items[0], LabelItem)

    def test_xform_parsing_with_repeat_group(self):
        form_xml = self.get_xml('repeat_group_form')

        schema = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            [],
            ['en'],
            self.app_id,
            1
        )

        self.assertEqual(len(schema.group_schemas), 2)

        group_schema = schema.group_schemas[0]
        self.assertEqual(len(group_schema.items), 2)
        self.assertEqual(group_schema.path, MAIN_TABLE)

        form_items = filter(lambda item: item.tag is None, group_schema.items)
        self.assertEqual(form_items[0].path, [PathNode(name='form'), PathNode(name='question1')])
        self.assertEqual(form_items[1].path, [PathNode(name='form'), PathNode(name='zendquestion')])

        group_schema = schema.group_schemas[1]
        self.assertEqual(len(group_schema.items), 1)
        self.assertEqual(
            group_schema.path,
            [PathNode(name='form'), PathNode(name='question3', is_repeat=True)]
        )
        self.assertEqual(
            group_schema.items[0].path,
            [PathNode(name='form'), PathNode(name='question3', is_repeat=True), PathNode(name='question4')]
        )

    def test_xform_parsing_with_multiple_choice(self):
        form_xml = self.get_xml('multiple_choice_form')
        schema = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            [],
            ['en'],
            self.app_id,
            1
        )

        self.assertEqual(len(schema.group_schemas), 1)
        group_schema = schema.group_schemas[0]

        self.assertEqual(len(group_schema.items), 2)
        form_items = filter(lambda item: item.tag is None, group_schema.items)
        self.assertEqual(form_items[0].path, [PathNode(name='form'), PathNode(name='question1')])

        self.assertEqual(form_items[1].path, [PathNode(name='form'), PathNode(name='question2')])
        self.assertEqual(form_items[1].options[0].value, 'choice1')
        self.assertEqual(form_items[1].options[1].value, 'choice2')

    def test_repeat_subcases_schema_generation(self):
        form_xml = self.get_xml('nested_repeat_form')
        repeats_with_subcases = [
            OpenSubCaseAction(
                repeat_context='/data/repeat',
                case_properties={
                    'weight': '/data/repeat/group/weight',
                }
            ),
            OpenSubCaseAction(
                repeat_context='/data/repeat/nested_repeat',
                case_properties={
                    'age': '/data/repeat/nested_repeat/age',
                }
            ),
        ]

        schema = FormExportDataSchema._generate_schema_from_repeat_subcases(
            XForm(form_xml),
            repeats_with_subcases,
            ['en'],
            self.app_id,
            1,
        )

        self.assertEqual(len(schema.group_schemas), 2)

        group_schema = schema.group_schemas[0]
        attribute_items = filter(lambda item: item.path[-1].name in CASE_ATTRIBUTES, group_schema.items)

        self.assertEqual(len(attribute_items), len(CASE_ATTRIBUTES))
        self.assertTrue(all(map(
            lambda item: item.readable_path.startswith('form.repeat.case'),
            attribute_items,
        )))

        create_items = filter(lambda item: item.path[-1].name in CASE_CREATE_ELEMENTS, group_schema.items)
        self.assertEqual(len(create_items), len(CASE_CREATE_ELEMENTS))
        self.assertTrue(all(map(
            lambda item: item.readable_path.startswith('form.repeat.case.create'),
            create_items,
        )))

        update_items = list(set(group_schema.items) - set(create_items) - set(attribute_items))
        self.assertEqual(len(update_items), 1)
        self.assertEqual(update_items[0].readable_path, 'form.repeat.case.update.group.weight')

    def test_xform_parsing_with_stock_questions(self):
        form_xml = self.get_xml('stock_form')
        schema = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            [],
            ['en'],
            self.app_id,
            1
        )
        self.assertEqual(len(schema.group_schemas), 1)
        group_schema = schema.group_schemas[0]

        self.assertEqual(len(group_schema.items), 6)
        self.assertTrue(all(map(lambda item: item.doc_type == 'StockItem', group_schema.items)))
        for parent_attr in ['@type', '@entity-id', '@date', '@section-id']:
            self.assertTrue(any(map(
                lambda item: item.path == [
                    PathNode(name='form'),
                    PathNode(name='balance:balance_one'),
                    PathNode(name=parent_attr),
                ],
                group_schema.items,
            )))

        for entry_attr in ['@id', '@quantity']:
            self.assertTrue(any(map(
                lambda item: item.path == [
                    PathNode(name='form'),
                    PathNode(name='balance:balance_one'),
                    PathNode(name='entry'),
                    PathNode(name=entry_attr),
                ],
                group_schema.items,
            )))

    def test_question_path_to_path_nodes(self):
        """
        Confirm that _question_path_to_path_nodes() works as expected
        """
        repeat_groups = [
            "/data/repeat1",
            "/data/group1/repeat2",
            "/data/group1/repeat2/repeat3",
        ]
        self.assertEqual(
            _question_path_to_path_nodes("/data/repeat1", repeat_groups),
            [PathNode(name='form', is_repeat=False), PathNode(name='repeat1', is_repeat=True)]
        )
        self.assertEqual(
            _question_path_to_path_nodes("/data/group1", repeat_groups),
            [PathNode(name='form', is_repeat=False), PathNode(name='group1', is_repeat=False)]
        )
        self.assertEqual(
            _question_path_to_path_nodes("/data/group1/repeat2", repeat_groups),
            [
                PathNode(name='form', is_repeat=False),
                PathNode(name='group1', is_repeat=False),
                PathNode(name='repeat2', is_repeat=True),
            ]
        )
        self.assertEqual(
            _question_path_to_path_nodes("/data/group1/repeat2/repeat3", repeat_groups),
            [
                PathNode(name='form', is_repeat=False),
                PathNode(name='group1', is_repeat=False),
                PathNode(name='repeat2', is_repeat=True),
                PathNode(name='repeat3', is_repeat=True),
            ]
        )
        self.assertEqual(
            _question_path_to_path_nodes("/data/group1/repeat2/repeat3/group2", repeat_groups),
            [
                PathNode(name='form', is_repeat=False),
                PathNode(name='group1', is_repeat=False),
                PathNode(name='repeat2', is_repeat=True),
                PathNode(name='repeat3', is_repeat=True),
                PathNode(name='group2', is_repeat=False),
            ]
        )

    def test_allow_non_data_nodes(self):
        """
        Ensure that we allow non data nodes
        """
        self.assertEqual(
            _question_path_to_path_nodes("/nodata/question", []),
            [
                PathNode(name='form', is_repeat=False),
                PathNode(name='question', is_repeat=False),
            ]
        )


class TestCaseExportDataSchema(SimpleTestCase, TestXmlMixin):
    app_id = '1234'

    def test_case_type_metadata_parsing(self):

        case_property_mapping = {
            'candy': ['my_case_property', 'my_second_case_property']
        }
        schema = CaseExportDataSchema._generate_schema_from_case_property_mapping(
            case_property_mapping,
            [],
            self.app_id,
            1,
        )
        self.assertEqual(len(schema.group_schemas), 1)
        group_schema = schema.group_schemas[0]

        my_case_property_item = group_schema.items[0]
        my_second_case_property_item = group_schema.items[1]
        self.assertEqual(my_case_property_item.path, [PathNode(name='my_case_property')])
        self.assertEqual(my_case_property_item.last_occurrences[self.app_id], 1)
        self.assertEqual(my_second_case_property_item.path, [PathNode(name='my_second_case_property')])
        self.assertEqual(my_second_case_property_item.last_occurrences[self.app_id], 1)

    def test_case_history_parsing(self):
        schema = CaseExportDataSchema._generate_schema_for_case_history({
            'candy': ['my_case_property', 'my_second_case_property']
        }, self.app_id, 1)

        self.assertEqual(len(schema.group_schemas), 1)
        group_schema = schema.group_schemas[0]

        update_items = filter(lambda item: item.tag == PROPERTY_TAG_UPDATE, group_schema.items)
        self.assertEqual(len(update_items), 2 + len(KNOWN_CASE_PROPERTIES))

    def test_get_app_build_ids_to_process(self):
        from corehq.apps.app_manager.dbaccessors import AppBuildVersion
        results = [
            AppBuildVersion(app_id='1', build_id='2', version=3),
            AppBuildVersion(app_id='1', build_id='4', version=5),
            AppBuildVersion(app_id='2', build_id='2', version=3),
        ]
        last_app_versions = {
            '1': 3
        }
        with patch(
                'corehq.apps.export.models.new.get_all_built_app_ids_and_versions',
                return_value=results):
            build_ids = CaseExportDataSchema._get_app_build_ids_to_process(
                'dummy',
                'dummy-app-id',
                last_app_versions
            )
        self.assertEqual(sorted(build_ids), ['2', '4'])


class TestMergingFormExportDataSchema(SimpleTestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)
    app_id = '1234'

    def _get_merged_schema(self, form_name1, form_name2):
        form_xml = self.get_xml(form_name1)
        form_xml2 = self.get_xml(form_name2)
        schema = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            [],
            ['en'],
            self.app_id,
            1
        )
        schema2 = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml2),
            [],
            ['en'],
            self.app_id,
            2
        )

        return FormExportDataSchema._merge_schemas(schema, schema2)

    def test_simple_merge(self):
        """Tests merging of a form that adds a question to the form"""
        merged = self._get_merged_schema('basic_form', 'basic_form_version2')

        self.assertEqual(len(merged.group_schemas), 1)

        group_schema = merged.group_schemas[0]
        self.assertEqual(len(group_schema.items), 3)
        self.assertTrue(all(map(
            lambda item: item.last_occurrences[self.app_id] == 2,
            group_schema.items,
        )))

    def test_merge_deleted(self):
        """Tests merging of a form that deletes a question from its form"""
        merged = self._get_merged_schema('basic_form', 'basic_form_version2_delete')

        self.assertEqual(len(merged.group_schemas), 1)

        group_schema = merged.group_schemas[0]
        self.assertEqual(len(group_schema.items), 2)

        v1items = filter(lambda item: item.last_occurrences[self.app_id] == 1, group_schema.items)
        v2items = filter(lambda item: item.last_occurrences[self.app_id] == 2, group_schema.items)

        self.assertEqual(
            len(v2items),
            1,
            'There should be 1 item that was found in the second version. There was {}'.format(len(v2items))
        )
        self.assertEqual(
            len(v1items),
            1,
            'There should be 1 item that was found in the first version. There was {}'.format(len(v1items))
        )

    def test_multiple_choice_merge(self):
        """Tests merging of a form that changes the options to a multiple choice question"""
        merged = self._get_merged_schema('multiple_choice_form', 'multiple_choice_form_version2')

        self.assertEqual(len(merged.group_schemas), 1)

        group_schema = merged.group_schemas[0]
        self.assertEqual(len(group_schema.items), 2)

        v2items = filter(lambda item: item.last_occurrences[self.app_id] == 2, group_schema.items)
        self.assertEqual(len(v2items), 2)

        multichoice = filter(
            lambda item: item.path == [PathNode(name='form'), PathNode(name='question2')],
            group_schema.items
        )[0]
        self.assertEqual(len(multichoice.options), 3)
        self.assertEqual(
            len(filter(lambda o: o.last_occurrences[self.app_id] == 2, multichoice.options)),
            2,
        )

        self.assertEqual(
            len(filter(lambda o: o.last_occurrences[self.app_id] == 1, multichoice.options)),
            1,
        )

    def test_merge_repeat_group_changed_id(self):
        """This tests merging forms that change a question to a repeat group"""
        merged = self._get_merged_schema('repeat_group_form', 'repeat_group_form_version2')

        self.assertEqual(len(merged.group_schemas), 2)
        group_schema1 = merged.group_schemas[0]
        group_schema2 = merged.group_schemas[1]

        self.assertEqual(group_schema1.last_occurrences[self.app_id], 2)
        self.assertEqual(len(group_schema1.items), 3)

        self.assertEqual(group_schema2.last_occurrences[self.app_id], 1)
        self.assertEqual(len(group_schema2.items), 1)


class TestMergingCaseExportDataSchema(SimpleTestCase, TestXmlMixin):

    def test_basic_case_prop_merge(self):
        app_id = '1234'
        case_property_mapping = {
            'candy': ['my_case_property', 'my_second_case_property']
        }
        schema1 = CaseExportDataSchema._generate_schema_from_case_property_mapping(
            case_property_mapping,
            [],
            app_id,
            1,
        )
        case_property_mapping = {
            'candy': ['my_case_property', 'my_third_case_property']
        }
        schema2 = CaseExportDataSchema._generate_schema_from_case_property_mapping(
            case_property_mapping,
            [],
            app_id,
            2,
        )
        schema3 = CaseExportDataSchema._generate_schema_for_case_history(
            case_property_mapping,
            app_id,
            2,
        )

        merged = CaseExportDataSchema._merge_schemas(schema1, schema2, schema3)

        self.assertEqual(len(merged.group_schemas), 2)
        group_schema1 = merged.group_schemas[0]
        group_schema2 = merged.group_schemas[1]

        self.assertEqual(group_schema1.last_occurrences[app_id], 2)
        self.assertEqual(len(group_schema1.items), 3)

        items = filter(lambda i: i.last_occurrences[app_id] == 1, group_schema1.items)
        self.assertEqual(len(items), 1)

        self.assertEqual(group_schema2.last_occurrences[app_id], 2)
        self.assertEqual(
            len(group_schema2.items),
            len(case_property_mapping['candy']) + len(KNOWN_CASE_PROPERTIES),
        )

    def test_inferred_schema_merge(self):
        schema = CaseExportDataSchema(
            domain='my-domain',
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[ExportItem(
                        path=[PathNode(name='case_property')]
                    )],
                )
            ]
        )
        inferred_schema = CaseExportDataSchema(
            domain='my-domain',
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[ExportItem(
                        path=[PathNode(name='case_property')],
                        inferred=True,
                        inferred_from=set(['One']),
                    )],
                    inferred=True,
                )
            ]
        )
        inferred_schema_two = CaseExportDataSchema(
            domain='my-domain',
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[ExportItem(
                        path=[PathNode(name='case_property')],
                        inferred=True,
                        inferred_from=set(['Two']),
                    )],
                    inferred=True,
                )
            ]
        )
        merged = ExportDataSchema._merge_schemas(schema, inferred_schema, inferred_schema_two)
        self.assertEqual(len(merged.group_schemas), 1)
        self.assertTrue(merged.group_schemas[0].inferred)
        group_schema = merged.group_schemas[0]
        self.assertEqual(len(group_schema.items), 1)
        self.assertTrue(group_schema.items[0].inferred)
        self.assertEqual(group_schema.items[0].inferred_from, set(['One', 'Two']))


class TestBuildingSchemaFromApplication(TestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)
    case_type = 'wonderwoman'
    domain = 'aspace'

    @classmethod
    def setUpClass(cls):
        cls.current_app = Application.wrap(cls.get_json('basic_application'))

        cls.first_build = Application.wrap(cls.get_json('basic_application'))
        cls.first_build._id = '123'
        cls.first_build.copy_of = cls.current_app.get_id
        cls.first_build.version = 3

        cls.advanced_app = Application.new_app('domain', "Untitled Application")
        module = cls.advanced_app.add_module(AdvancedModule.new_module('Untitled Module', None))
        form = module.new_form("Untitled Form", cls.get_xml('repeat_group_form'))
        form.xmlns = 'repeat-xmlns'
        form.actions.open_cases = [
            AdvancedOpenCaseAction(
                case_type="advanced",
                case_tag="open_case_0",
                name_path="/data/question3/question4",
                repeat_context="/data/question3",
            )
        ]

        cls.apps = [
            cls.current_app,
            cls.first_build,
            cls.advanced_app,
        ]
        with drop_connected_signals(app_post_save):
            for app in cls.apps:
                app.save()

        cls.inferred_schema = InferredSchema(
            domain=cls.domain,
            case_type=cls.case_type,
            group_schemas=[
                InferredExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='case_property')],
                            label='Inferred 1',
                            inferred=True
                        ),
                        ExportItem(
                            path=[PathNode(name='data'), PathNode(name='case_property_2')],
                            label='Inferred 1',
                            inferred=True
                        ),
                    ],
                    inferred=True
                ),
            ]
        )
        cls.inferred_schema.save()

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps:
            app.delete()
        cls.inferred_schema.delete()

    def tearDown(self):
        delete_all_export_data_schemas()

    def test_basic_application_schema(self):
        app = self.current_app

        schema = FormExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            'my_sweet_xmlns'
        )

        self.assertEqual(len(schema.group_schemas), 1)

    def test_build_from_saved_schema(self):
        app = self.current_app

        schema = FormExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            'my_sweet_xmlns'
        )

        self.assertEqual(len(schema.group_schemas), 1)
        self.assertEqual(schema.last_app_versions[app._id], app.version)

        # After the first schema has been saved let's add a second app to process
        second_build = Application.wrap(self.get_json('basic_application'))
        second_build._id = '456'
        second_build.copy_of = app.get_id
        second_build.version = 6
        second_build.save()
        self.addCleanup(second_build.delete)

        new_schema = FormExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            'my_sweet_xmlns'
        )

        self.assertEqual(new_schema._id, schema._id)
        self.assertEqual(new_schema.last_app_versions[app._id], app.version)
        self.assertEqual(len(new_schema.group_schemas), 1)

    def test_build_with_inferred_schema(self):
        app = self.current_app

        schema = CaseExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            self.case_type,
        )

        group_schema = schema.group_schemas[0]
        self.assertEqual(group_schema.path, MAIN_TABLE)
        self.assertTrue(group_schema.inferred)
        inferred_items = filter(lambda item: item.inferred, group_schema.items)
        self.assertEqual(len(inferred_items), 2)

    def test_build_with_advanced_app(self):
        app = self.advanced_app

        schema = FormExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            "repeat-xmlns",
        )

        group_schema = schema.group_schemas[1]  # The repeat schema

        # Assert that all proper case attributes are added to advanced forms that open
        # cases with repeats
        path_suffixes = set(map(lambda item: item.path[-1].name, group_schema.items))
        self.assertEqual(len(path_suffixes & set(CASE_ATTRIBUTES)), len(CASE_ATTRIBUTES))


class TestExportDataSchemaVersionControl(TestCase, TestXmlMixin):

    file_path = ['data']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        cls.current_app = Application.wrap(cls.get_json('basic_application'))
        with drop_connected_signals(app_post_save):
            cls.current_app.save()

    @classmethod
    def tearDownClass(cls):
        cls.current_app.delete()

    def tearDown(self):
        delete_all_export_data_schemas()
        super(TestExportDataSchemaVersionControl, self).tearDown()

    def test_rebuild_version_control(self):
        app = self.current_app

        schema = FormExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            'my_sweet_xmlns'
        )

        existing_schema = FormExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            'my_sweet_xmlns'
        )
        self.assertEqual(schema._id, existing_schema._id)

        with patch(
                'corehq.apps.export.models.new.FORM_DATA_SCHEMA_VERSION',
                FORM_DATA_SCHEMA_VERSION + 1):
            rebuilt_schema = FormExportDataSchema.generate_schema_from_builds(
                app.domain,
                app._id,
                'my_sweet_xmlns'
            )
        self.assertNotEqual(schema._id, rebuilt_schema._id)
        self.assertEqual(schema.version, FORM_DATA_SCHEMA_VERSION)
        self.assertEqual(rebuilt_schema.version, FORM_DATA_SCHEMA_VERSION + 1)


class TestBuildingCaseSchemaFromApplication(TestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)
    domain = 'aspace'
    case_type = 'candy'

    @classmethod
    def setUpClass(cls):
        cls.current_app = Application.wrap(cls.get_json('basic_case_application'))

        cls.first_build = Application.wrap(cls.get_json('basic_case_application'))
        cls.first_build._id = '123'
        cls.first_build.copy_of = cls.current_app.get_id
        cls.first_build.version = 3

        cls.apps = [
            cls.current_app,
            cls.first_build,
        ]
        with drop_connected_signals(app_post_save):
            for app in cls.apps:
                app.save()

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps:
            app.delete()

    def tearDown(self):
        delete_all_export_data_schemas()
        delete_all_inferred_schemas()

    def test_basic_application_schema(self):
        schema = CaseExportDataSchema.generate_schema_from_builds(
            self.domain,
            self.current_app._id,
            self.case_type,
        )

        # One for case, one for case history
        self.assertEqual(len(schema.group_schemas), 2)

        group_schema = schema.group_schemas[0]
        self.assertEqual(group_schema.last_occurrences[self.current_app._id], self.current_app.version)
        self.assertEqual(len(group_schema.items), 2)

    def test_build_from_saved_schema(self):
        app = self.current_app

        schema = CaseExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            self.case_type,
        )

        self.assertEqual(schema.last_app_versions[app._id], app.version)
        # One for case, one for case history
        self.assertEqual(len(schema.group_schemas), 2)

        # After the first schema has been saved let's add a second app to process
        second_build = Application.wrap(self.get_json('basic_case_application'))
        second_build._id = '456'
        second_build.copy_of = app.get_id
        second_build.version = 6
        with drop_connected_signals(app_post_save):
            second_build.save()
        self.addCleanup(second_build.delete)

        new_schema = CaseExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            self.case_type,
        )

        self.assertEqual(new_schema._id, schema._id)
        self.assertEqual(new_schema.last_app_versions[app._id], app.version)
        # One for case, one for case history
        self.assertEqual(len(new_schema.group_schemas), 2)

    def test_build_with_inferred_schema(self):
        app = self.current_app

        schema = CaseExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            self.case_type,
        )
        # Main table
        group_schema = schema.group_schemas[0]
        self.assertEqual(len(group_schema.items), 2)

        add_inferred_export_properties(
            'TestSend',
            app.domain,
            self.case_type,
            ['question2', 'new-property'],
        )

        schema = CaseExportDataSchema.generate_schema_from_builds(
            app.domain,
            app._id,
            self.case_type,
        )
        # Main table
        group_schema = schema.group_schemas[0]

        # Only the new property should be added. The repeated one should be merged
        self.assertEqual(len(group_schema.items), 3)


class TestBuildingCaseSchemaFromMultipleApplications(TestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)
    domain = 'aspace'
    case_type = 'candy'

    @classmethod
    def setUpClass(cls):
        cls.current_app = Application.wrap(cls.get_json('basic_case_application'))

        cls.first_build = Application.wrap(cls.get_json('basic_case_application'))
        cls.first_build._id = '123'
        cls.first_build.copy_of = cls.current_app.get_id
        cls.first_build.version = 3

        cls.other_build = Application.wrap(cls.get_json('basic_case_application'))
        cls.other_build._id = '456'
        cls.other_build.copy_of = 'other-app-id'
        cls.other_build.version = 4
        cls.other_build.has_submissions = True

        cls.apps = [
            cls.current_app,
            cls.first_build,
            cls.other_build,
        ]
        with drop_connected_signals(app_post_save):
            for app in cls.apps:
                app.save()

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps:
            app.delete()

    def tearDown(self):
        delete_all_export_data_schemas()

    def test_multiple_app_schema_generation(self):
        schema = CaseExportDataSchema.generate_schema_from_builds(
            self.domain,
            self.current_app._id,
            self.case_type,
        )

        self.assertEqual(
            schema.last_app_versions[self.other_build.copy_of],
            self.other_build.version,
        )
        # One for case, one for case history
        self.assertEqual(len(schema.group_schemas), 2)

        group_schema = schema.group_schemas[0]
        self.assertEqual(group_schema.last_occurrences[self.current_app._id], self.current_app.version)
        self.assertEqual(len(group_schema.items), 2)


class TestBuildingParentCaseSchemaFromApplication(TestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)
    domain = 'aspace'
    case_type = 'candy'

    @classmethod
    def setUpClass(cls):
        cls.current_app = Application.wrap(cls.get_json('parent_child_case_application'))
        cls.current_app.copy_of = None

        cls.apps = [
            cls.current_app,
        ]
        with drop_connected_signals(app_post_save):
            for app in cls.apps:
                app.save()

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps:
            app.delete()

    def tearDown(self):
        delete_all_export_data_schemas()

    def test_parent_case_table_generation(self):
        """
        Ensures that the child case generates a parent case table and indices
        columns in main table
        """
        schema = CaseExportDataSchema.generate_schema_from_builds(
            self.domain,
            self.current_app._id,
            'child-case',
        )

        # One for case, one for case history, one for parent case
        self.assertEqual(len(schema.group_schemas), 3)
        main_table = filter(lambda gs: gs.path == MAIN_TABLE, schema.group_schemas)[0]
        self.assertEqual(
            len(filter(lambda item: item.doc_type == 'CaseIndexItem', main_table.items)),
            1
        )

        self.assertEqual(
            len(filter(lambda gs: gs.path == PARENT_CASE_TABLE, schema.group_schemas)),
            1
        )

    def test_parent_case_table_generation_for_parent_case(self):
        """Ensures that the parent case doesn't have a parent case table"""
        schema = CaseExportDataSchema.generate_schema_from_builds(
            self.domain,
            self.current_app._id,
            self.case_type,
        )

        # One for case, one for case history
        self.assertEqual(len(schema.group_schemas), 2)
