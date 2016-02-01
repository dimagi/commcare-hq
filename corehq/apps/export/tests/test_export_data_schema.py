import os
from mock import patch

from django.test import SimpleTestCase, TestCase
from dimagi.utils.couch.database import safe_delete
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.app_manager.models import XForm, Application
from corehq.apps.export.models import FormExportDataSchema, CaseExportDataSchema, ExportDataSchema
from corehq.apps.export.const import CASE_HISTORY_PROPERTIES, PROPERTY_TAG_UPDATE


class TestFormExportDataSchema(SimpleTestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)
    app_id = '1234'

    def test_basic_xform_parsing(self):
        form_xml = self.get_xml('basic_form')

        schema = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            ['en'],
            self.app_id,
            1
        )

        self.assertEqual(len(schema.group_schemas), 1)

        group_schema = schema.group_schemas[0]

        self.assertEqual(len(group_schema.items), 2)
        self.assertEqual(group_schema.items[0].path, ['data', 'question1'])
        self.assertEqual(group_schema.items[1].path, ['data', 'question2'])

    def test_xform_parsing_with_repeat_group(self):
        form_xml = self.get_xml('repeat_group_form')

        schema = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            ['en'],
            self.app_id,
            1
        )

        self.assertEqual(len(schema.group_schemas), 2)

        group_schema = schema.group_schemas[0]
        self.assertEqual(len(group_schema.items), 1)
        self.assertEqual(group_schema.path, None)
        self.assertEqual(group_schema.items[0].path, ['data', 'question1'])

        group_schema = schema.group_schemas[1]
        self.assertEqual(len(group_schema.items), 1)
        self.assertEqual(group_schema.path, ['data', 'question3'])
        self.assertEqual(group_schema.items[0].path, ['data', 'question3', 'question4'])

    def test_xform_parsing_with_multiple_choice(self):
        form_xml = self.get_xml('multiple_choice_form')
        schema = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml),
            ['en'],
            self.app_id,
            1
        )

        self.assertEqual(len(schema.group_schemas), 1)
        group_schema = schema.group_schemas[0]

        self.assertEqual(len(group_schema.items), 2)
        self.assertEqual(group_schema.items[0].path, ['data', 'question1'])

        self.assertEqual(group_schema.items[1].path, ['data', 'question2'])
        self.assertEqual(group_schema.items[1].options[0].value, 'choice1')
        self.assertEqual(group_schema.items[1].options[1].value, 'choice2')


class TestCaseExportDataSchema(SimpleTestCase, TestXmlMixin):
    app_id = '1234'

    def test_case_type_metadata_parsing(self):

        case_property_mapping = {
            'candy': ['my_case_property', 'my_second_case_property']
        }
        schema = CaseExportDataSchema._generate_schema_from_case_property_mapping(
            case_property_mapping,
            self.app_id,
            1,
        )
        self.assertEqual(len(schema.group_schemas), 1)
        group_schema = schema.group_schemas[0]

        self.assertEqual(group_schema.items[0].path, ['my_case_property'])
        self.assertEqual(group_schema.items[0].last_occurrences[self.app_id], 1)
        self.assertEqual(group_schema.items[1].path, ['my_second_case_property'])
        self.assertEqual(group_schema.items[1].last_occurrences[self.app_id], 1)

    def test_case_history_parsing(self):
        schema = CaseExportDataSchema._generate_schema_for_case_history({
            'candy': ['my_case_property', 'my_second_case_property']
        }, self.app_id, 1)

        self.assertEqual(len(schema.group_schemas), 1)
        group_schema = schema.group_schemas[0]

        for idx, prop in enumerate(CASE_HISTORY_PROPERTIES):
            self.assertEqual(group_schema.items[idx].path, [prop.name])
            self.assertEqual(group_schema.items[idx].tag, prop.tag)

        update_items = filter(lambda item: item.tag == PROPERTY_TAG_UPDATE, group_schema.items)
        self.assertEqual(len(update_items), 2)

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
            ['en'],
            self.app_id,
            1
        )
        schema2 = FormExportDataSchema._generate_schema_from_xform(
            XForm(form_xml2),
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
        self.assertEqual(
            len(v2items),
            2,
        )

        multichoice = filter(lambda item: item.path == ['data', 'question2'], group_schema.items)[0]
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
        self.assertEqual(len(group_schema1.items), 2)

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
            app_id,
            1,
        )
        case_property_mapping = {
            'candy': ['my_case_property', 'my_third_case_property']
        }
        schema2 = CaseExportDataSchema._generate_schema_from_case_property_mapping(
            case_property_mapping,
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
            len(CASE_HISTORY_PROPERTIES) + len(case_property_mapping['candy'])
        )


class TestBuildingSchemaFromApplication(TestCase, TestXmlMixin):
    file_path = ['data']
    root = os.path.dirname(__file__)

    @classmethod
    def setUpClass(cls):
        cls.current_app = Application.wrap(cls.get_json('basic_application'))

        cls.first_build = Application.wrap(cls.get_json('basic_application'))
        cls.first_build._id = '123'
        cls.first_build.copy_of = cls.current_app.get_id
        cls.first_build.version = 3

        cls.apps = [
            cls.current_app,
            cls.first_build,
        ]
        for app in cls.apps:
            app.save()

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps:
            app.delete()
        # to circumvent domain.delete()'s recursive deletion that this test doesn't need

    def tearDown(self):
        db = ExportDataSchema.get_db()
        for row in db.view('schemas_by_xmlns_or_case_type/view', reduce=False):
            doc_id = row['id']
            safe_delete(db, doc_id)

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
        self.assertEqual(schema.last_app_versions[app._id], 3)

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

        self.assertNotEqual(new_schema._id, schema._id)
        self.assertEqual(new_schema.last_app_versions[app._id], 6)
        self.assertEqual(len(new_schema.group_schemas), 1)


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
        for app in cls.apps:
            app.save()

    @classmethod
    def tearDownClass(cls):
        for app in cls.apps:
            app.delete()

    def tearDown(self):
        db = ExportDataSchema.get_db()
        for row in db.view('schemas_by_xmlns_or_case_type/view', reduce=False):
            doc_id = row['id']
            safe_delete(db, doc_id)

    def test_basic_application_schema(self):
        schema = CaseExportDataSchema.generate_schema_from_builds(self.domain, self.case_type)

        self.assertEqual(len(schema.group_schemas), 2)

        group_schema = schema.group_schemas[0]
        self.assertEqual(group_schema.last_occurrences[self.current_app._id], 3)
        self.assertEqual(len(group_schema.items), 2)

    def test_build_from_saved_schema(self):
        app = self.current_app

        schema = CaseExportDataSchema.generate_schema_from_builds(
            app.domain,
            self.case_type,
        )

        self.assertEqual(schema.last_app_versions[app._id], 3)
        self.assertEqual(len(schema.group_schemas), 2)

        # After the first schema has been saved let's add a second app to process
        second_build = Application.wrap(self.get_json('basic_case_application'))
        second_build._id = '456'
        second_build.copy_of = app.get_id
        second_build.version = 6
        second_build.save()
        self.addCleanup(second_build.delete)

        new_schema = CaseExportDataSchema.generate_schema_from_builds(
            app.domain,
            self.case_type,
        )

        self.assertNotEqual(new_schema._id, schema._id)
        self.assertEqual(new_schema.last_app_versions[app._id], 6)
        self.assertEqual(len(new_schema.group_schemas), 2)
