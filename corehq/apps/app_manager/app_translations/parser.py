from __future__ import absolute_import

import re
from datetime import datetime
from openpyxl import Workbook
from tempfile import NamedTemporaryFile

from corehq.apps.app_manager.app_translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.dump_reload.const import DATETIME_FORMAT


class TranslationsParser:
    def __init__(self, transifex):
        self.transifex = transifex
        self.translations = {}
        self.key_lang_str = '{}{}'.format(self.transifex.lang_prefix, self.transifex.key_lang)
        self.source_lang_str = '{}{}'.format(self.transifex.lang_prefix, self.transifex.source_lang)

    def _parse_sheet(self, ws, po_entries):
        """
        :param ws: workbook sheet object
        :param po_entries: list of POEntry Objects to read translations from
        :return:
        """
        sheet_name = ws.title
        if sheet_name == MODULES_AND_FORMS_SHEET_NAME:
            self._parse_module_and_form_sheet(ws, po_entries)
        elif 'module' in sheet_name and 'form' not in sheet_name:
            self._parse_module_sheet(ws, po_entries)
        elif 'module' in sheet_name and 'form' in sheet_name:
            self._parse_form_sheet(ws, po_entries)
        else:
            raise Exception("Got unexpected sheet name %s" % sheet_name)

    def _parse_module_and_form_sheet(self, ws, po_entries):
        # expected context format
        # index:Module or Form: sheet name for module/form: unique id
        context_regex = r'^(\d+):(Module|Form):(\w+):(\w+)$'
        ws.append(["Type", "sheet_name", self.key_lang_str, self.source_lang_str, 'unique_id'])
        for po_entry in po_entries:
            context = po_entry.msgctxt
            _index, _type, _sheet_name, _unique_id = re.match(context_regex, context).groups()
            ws.append([_type, _sheet_name, po_entry.msgid, po_entry.msgstr, _unique_id])
            self.translations[ws.title].append(
                {
                    'Type': _type,
                    'sheet_name': _sheet_name,
                    self.key_lang_str: po_entry.msgid,
                    self.source_lang_str: po_entry.msgstr,
                    'unique_id': _unique_id
                }
            )

    def _parse_module_sheet(self, ws, po_entries):
        # expected context format
        # index: case property: list/detail
        context_regex = r'^(\d+):(.+):(list|detail)$'
        ws.append(["case_property", "list_or_detail", self.key_lang_str, self.source_lang_str])
        for po_entry in po_entries:
            context = po_entry.msgctxt
            _index, _case_property, _list_or_detail = re.match(context_regex, context).groups()
            ws.append([_case_property, _list_or_detail, po_entry.msgid, po_entry.msgstr])
            self.translations[ws.title].append(
                {
                    'case_property': _case_property,
                    'list_or_detail': _list_or_detail,
                    self.key_lang_str: po_entry.msgid,
                    self.source_lang_str: po_entry.msgstr
                }
            )

    def _parse_form_sheet(self, ws, po_entries):
        # expected context regex
        # index: label
        context_regex = r'^(\d+):(.+)$'
        ws.append(["label", self.key_lang_str, self.source_lang_str])
        for po_entry in po_entries:
            context = po_entry.msgctxt
            _index, _label = re.match(context_regex, context).groups()
            ws.append([_label, po_entry.msgid, po_entry.msgstr])
            self.translations[ws.title].append(
                {
                    'label': _label,
                    self.key_lang_str: po_entry.msgid,
                    self.source_lang_str: po_entry.msgstr
                }
            )

    def result_file_name(self, version):
        return ("TransifexTranslations {}-{}:v{} {}.xlsx".format(
            self.transifex.key_lang, self.transifex.source_lang,
            version, datetime.utcnow().strftime(DATETIME_FORMAT))
        )

    def _generate_sheets(self, wb, resource_slugs):
        version = self.transifex.version
        all_translations = self.transifex.get_translations(version, resource_slugs)
        for resource_name in all_translations:
            po_entries = all_translations[resource_name]
            sheet_name = resource_name.split("_v%s" % version)[0]
            self.translations[sheet_name] = []
            ws = wb.create_sheet(title=sheet_name)
            self._parse_sheet(ws, po_entries)

    def generate_excel_file(self, resource_slugs=None):
        version = self.transifex.version
        wb = Workbook(write_only=True)
        self._generate_sheets(wb, resource_slugs)

        with NamedTemporaryFile(delete=False) as tempfile:
            wb.save(tempfile)
            return tempfile, self.result_file_name(version)
