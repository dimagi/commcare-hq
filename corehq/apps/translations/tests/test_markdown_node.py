# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

import os
from io import BytesIO

from django.test import SimpleTestCase
from mock import patch

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.translations.app_translations.upload_form import BulkAppTranslationFormUpdater
from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.util.workbook_json.excel import WorkbookJSONReader
from couchexport.export import export_raw
from couchexport.models import Format


class AggregateMarkdownNodeTests(SimpleTestCase, TestXmlMixin):
    root = os.path.dirname(__file__)

    file_path = ('data', 'bulk_app_translation', 'aggregate')

    headers = (
        (MODULES_AND_FORMS_SHEET_NAME, (
            'Type', 'menu_or_form', 'default_en', 'default_afr', 'default_fra', 'image_en', 'image_afr',
            'image_fra', 'audio_en', 'audio_afr', 'audio_fra', 'unique_id',
        )),
        ('menu1', (
            'case_property', 'list_or_detail', 'default_en', 'default_fra', 'default_fra',
        )),
        ('menu1_form1', (
            'label', 'default_en', 'default_afr', 'default_fra', 'audio_en', 'audio_afr', 'audio_fra', 'image_en',
            'image_afr', 'image_fra', 'video_en', 'video_afr', 'video_fra',
        ))
    )
    data = (
        (MODULES_AND_FORMS_SHEET_NAME, (
            (
                'Menu', 'menu1', 'Untitled Module', 'Ongetitelde Module', 'Module Sans Titre', '', '', '', '', '',
                '', 'deadbeef'
            ),
            (
                'Form', 'menu1_form1', 'Untitled Form', 'Ongetitelde Form', 'Formulaire Sans Titre', '', '', '',
                '', '', '', 'c0ffee'
            )
        )),
        ('menu1', (
            (
                'name', 'list', 'Name', 'Naam', 'Nom'
            ), (
                'name', 'detail', 'Name', 'Naam', 'Nom'
            )
        )),
        ('menu1_form1', (
            (
                'with_markdown-label', '*With* Markdown', '*Met* Markdown', '*Avec* le Markdown', '', '', '', '',
                '', '', '', '', ''
            ), (
                'markdown_veto-label', '*Without* Markdown', '*Sonder* Markdown', '*Sans* le Markdown', '', '',
                '', '', '', '', '', '', ''
            )
        ))
    )

    def get_worksheet(self, title):
        string_io = BytesIO()
        export_raw(self.headers, self.data, string_io, format=Format.XLS_2007)
        string_io.seek(0)
        workbook = WorkbookJSONReader(string_io)  # __init__ will read string_io
        return workbook.worksheets_by_title[title]

    def setUp(self):
        self.app = Application.new_app('domain', "Untitled Application")
        self.app.langs = ['en', 'afr', 'fra']
        module1 = self.app.add_module(Module.new_module('module', None))
        form1 = self.app.new_form(module1.id, "Untitled Form", None)
        form1.source = self.get_xml('initial_xform').decode('utf-8')

        self.form1_worksheet = self.get_worksheet('menu1_form1')

    def test_markdown_node(self):
        """
        If one translation has a Markdown node, the label should be a Markdown label
        If Markdown is vetoed for one language, it should be vetoed for the label
        """
        sheet = self.form1_worksheet
        with patch('corehq.apps.translations.app_translations.upload_form.save_xform') as save_xform_patch:
            names_map = {}
            updater = BulkAppTranslationFormUpdater(self.app, sheet.worksheet.title, names_map)
            msgs = updater.update(sheet)
            self.assertEqual(msgs, [])
            expected_xform = self.get_xml('expected_xform').decode('utf-8')
            self.maxDiff = None
            self.assertEqual(save_xform_patch.call_args[0][2].decode('utf-8'), expected_xform)
