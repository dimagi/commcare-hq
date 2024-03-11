import os

from django.test import TestCase

from unittest.mock import patch

from couchexport.models import Format

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.signals import app_post_save
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.export.dbaccessors import delete_all_export_data_schemas
from corehq.apps.export.models import FormExportDataSchema, FormExportInstance
from corehq.apps.export.tests.util import (
    assertContainsExportItems,
    get_export_json,
)
from corehq.util.context_managers import drop_connected_signals


class TestFormExportSubcases(TestCase, TestXmlMixin):
    """
    These tests operate on an MCH app which uses various means of creating cases.
    We care most about module 0 ("Mothers") > form 1 ("Followup Form")
    The primary case type is "mom" - this form updates mom cases, but doesn't create them
    This form creates a single "voucher" case using the normal case management interface
        case_name is set to /data/voucher-name
    This form creates "baby" cases in a repeat group also using the normal case management interface
        case_name is set to /data/babies/whats_the_babys_name
    A "prescription" case can also be created using save-to-case.
        case_name is /data/prescription/prescription_name
        the save-to-case node is /data/prescription/prescription

    SK Update 2018-07-30:
      - http://manage.dimagi.com/default.asp?280515
      - added case update tha references a question outside of the repeat group (facility_name)
    """
    file_path = ['data']
    root = os.path.dirname(__file__)
    domain = 'app_with_subcases'
    app_json_file = 'app_with_subcases'
    form_xml_file = 'app_with_subcases_form'
    form_es_response_file = 'app_with_subcases_submission'
    form_xmlns = "http://openrosa.org/formdesigner/EA845CA3-4B57-47C4-AFF4-5884E40228D7"

    @classmethod
    def setUpClass(cls):
        super(TestFormExportSubcases, cls).setUpClass()
        cls.app = Application.wrap(cls.get_json(cls.app_json_file))
        cls.app.get_forms_by_xmlns(cls.form_xmlns)[0].source = cls.get_xml(cls.form_xml_file).decode('utf-8')
        with drop_connected_signals(app_post_save):
            cls.app.save()

        cls.form_es_response = cls.get_json(cls.form_es_response_file)

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        delete_all_export_data_schemas()
        super(TestFormExportSubcases, cls).tearDownClass()

    def test(self):
        schema = FormExportDataSchema.generate_schema(
            self.domain,
            self.app._id,
            self.form_xmlns,
            only_process_current_builds=True,
        )

        for group_schema in schema.group_schemas:
            # group_schema is an instance of ExportGroupSchem
            # group_schema.items is an array of ExportItems subclasses
            path = [node.name for node in group_schema.path]
            if path == []:
                main_group_schema = group_schema
            elif path == ['form', 'babies']:
                baby_repeat_group_schema = group_schema

        assertContainsExportItems(
            [
                # Verify that a simple form question appears in the schema
                ('form.how_are_you_today', 'How are you today?'),
                ('form.how_many_babies', 'How many babies?'),
                ('form.add_a_prescription', 'Add a prescription?'),
                ('form.voucher-name', '#form/voucher-name'),
                ('form.is_this_a_delivery', 'Is this a delivery?'),
                ('form.facility_name', '#form/facility_name'),

                # Verify that the main parent case updates appear (case type "mom")
                ('form.case.@case_id', 'case.@case_id'),
                ('form.case.@date_modified', 'case.@date_modified'),
                ('form.case.@user_id', 'case.@user_id'),
                ('form.case.update.last_status', 'case.update.last_status'),

                # Verify that we see case updates for save-to-case cases
                # These are already in the form schema, so they get interpreted like any other question
                ('form.prescription.prescription.case.close',
                 '#form/prescription/prescription/case/close'),
                ('form.prescription.prescription.case.create.case_name',
                 '#form/prescription/prescription/case/create/case_name'),
                ('form.prescription.prescription.case.create.case_type',
                 '#form/prescription/prescription/case/create/case_type'),
                ('form.prescription.prescription.case.update.number_of_babies',
                 '#form/prescription/prescription/case/update/number_of_babies'),
                ('form.prescription.prescription_name',
                 '#form/prescription/prescription_name'),
                ('form.prescription.prescription.case.index.parent',
                 '#form/prescription/prescription/case/index/parent'),
                ('form.prescription.prescription.case.@case_id',
                 '#form/prescription/prescription/case/@case_id'),
                ('form.prescription.prescription.case.@user_id',
                 '#form/prescription/prescription/case/@user_id'),
                ('form.prescription.prescription.case.@date_modified',
                 '#form/prescription/prescription/case/@date_modified'),

                # # Verify that we see updates from subcases not in repeat groups (case type "voucher")
                ('form.subcase_0.case.@case_id', 'subcase_0.@case_id'),
                ('form.subcase_0.case.@date_modified', 'subcase_0.@date_modified'),
                ('form.subcase_0.case.@user_id', 'subcase_0.@user_id'),
                ('form.subcase_0.case.create.case_name', 'subcase_0.create.case_name'),
                ('form.subcase_0.case.create.case_type', 'subcase_0.create.case_type'),
                ('form.subcase_0.case.create.owner_id', 'subcase_0.create.owner_id'),
                ('form.subcase_0.case.index.parent.#text', 'subcase_0.index.#text'),
                ('form.subcase_0.case.index.parent.@case_type', 'subcase_0.index.@case_type'),
                ('form.subcase_0.case.update.how_many_babies', 'subcase_0.update.how_many_babies'),

            ],
            main_group_schema
        )

        # Verify that we see updates from subcases in repeat groups (case type "baby")
        assertContainsExportItems(
            [
                ('form.babies.case.@case_id', 'subcase_1.@case_id'),
                ('form.babies.case.@date_modified', 'subcase_1.@date_modified'),
                ('form.babies.case.@user_id', 'subcase_1.@user_id'),
                ('form.babies.case.create.case_name', 'subcase_1.create.case_name'),
                ('form.babies.case.create.case_type', 'subcase_1.create.case_type'),
                ('form.babies.case.create.owner_id', 'subcase_1.create.owner_id'),
                ('form.babies.case.update.eye_color', 'subcase_1.update.eye_color'),
                ('form.babies.case.update.facility_name', 'subcase_1.update.facility_name'),
                ('form.babies.case.index.parent.#text', 'subcase_1.index.#text'),
                ('form.babies.case.index.parent.@case_type', 'subcase_1.index.@case_type'),
                ('form.babies.eye_color', 'Eye color?'),
                ('form.babies.whats_the_babys_name', "What's the baby's name?"),
            ],
            baby_repeat_group_schema
        )

        with patch("couchforms.analytics.get_form_count_breakdown_for_domain", lambda *a: {}):
            instance = FormExportInstance.generate_instance_from_schema(schema)
        instance.export_format = Format.JSON
        # make everything show up in the export
        for table in instance.tables:
            table.selected = True
            for column in table.columns:
                if column.item.path[-1].name == '@case_id' and not column.item.transform:
                    self.assertFalse(column.is_advanced)
                column.selected = True

        with patch('corehq.apps.export.export.get_export_documents') as docs:
            docs.return_value = self.form_es_response
            export_data = get_export_json(instance)

        def get_form_data(table):
            headers = export_data[table]['headers']
            return [
                dict(zip(headers, row))
                for row in export_data[table]['rows']
            ]

        form_data = get_form_data('Forms')[0]
        for key, value in {
            # normal form questions
            "form.add_a_prescription": "yes_then_close",
            "form.how_are_you_today": "fine_thanks",
            "form.how_many_babies": "2",
            "form.is_this_a_delivery": "yes",
            "form.voucher-name": "Petunia2017-08-29",

            # standard case update
            "form.case.update.last_status": "fine_thanks",
            "form.case.@case_id": "71626d9c-2d05-491f-81d9-becf8566618a",
            "form.case.@user_id": "853a24735ba89a3019ced7e3153dc60d",

            # save-to-case properties
            "form.prescription.prescription.case.close": "True",
            "form.prescription.prescription.case.create.case_name": "Petunia-prescription-2017-08-29",
            "form.prescription.prescription.case.create.case_type": "prescription",
            "form.prescription.prescription.case.update.number_of_babies": "2",
            "form.prescription.prescription_name": "Petunia-prescription-2017-08-29",
            "form.prescription.prescription.case.index.parent": "71626d9c-2d05-491f-81d9-becf8566618a",

            # non-repeating subcase actions
            "form.subcase_0.case.@case_id": "16954d55-a9be-40dd-98a8-dc7fae9c7ed6",
            "form.subcase_0.case.@date_modified": "2017-08-29 11:19:40",
            "form.subcase_0.case.@user_id": "853a24735ba89a3019ced7e3153dc60d",
            "form.subcase_0.case.create.case_name": "Petunia2017-08-29",
            "form.subcase_0.case.create.case_type": "voucher",
            "form.subcase_0.case.create.owner_id": "853a24735ba89a3019ced7e3153dc60d",
            "form.subcase_0.case.update.how_many_babies": "2",
            "form.subcase_0.case.index.parent.#text": "71626d9c-2d05-491f-81d9-becf8566618a",
            "form.subcase_0.case.index.parent.@case_type": "mom",

        }.items():
            self.assertEqual(form_data[key], value, f"key: {key!r}")

        self.assertDictEqual({
            "number": "0.0",
            "number__0": 0,
            "number__1": 0,

            "form.babies.eye_color": "brown",
            "form.babies.whats_the_babys_name": "Bob",

            "form.babies.case.@case_id": "5539bd9d-d5d6-44c8-8f78-6915f16b6907",
            "form.babies.case.@date_modified": "2017-08-29 11:19:40",
            "form.babies.case.@user_id": "853a24735ba89a3019ced7e3153dc60d",

            "form.babies.case.create.case_name": "Bob",
            "form.babies.case.create.case_type": "baby",
            "form.babies.case.create.owner_id": "853a24735ba89a3019ced7e3153dc60d",

            "form.babies.case.index.parent.#text": "71626d9c-2d05-491f-81d9-becf8566618a",
            "form.babies.case.index.parent.@case_type": "mom",

            "form.babies.case.update.eye_color": "brown",
            "form.babies.case.update.facility_name": "test",

        }, get_form_data('Repeat- babies')[0])
