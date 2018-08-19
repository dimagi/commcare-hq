from __future__ import absolute_import
from __future__ import unicode_literals

import re
from datetime import datetime
from openpyxl import Workbook
from tempfile import NamedTemporaryFile
from memoized import memoized

from corehq.apps.app_manager.app_translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.dump_reload.const import DATETIME_FORMAT


CONTEXT_REGEXS = {
    # index:Module or Form: sheet name for module/form: unique id
    'module_and_forms_sheet': r'^(\d+):(Module|Form):(\w+):(\w+)$',
    # index: case property: list/detail
    'module_sheet': r'^(\d+):(.+):(list|detail)$',
    # index: label
    'form_sheet': r'^(\d+):(.+)$',
}


class TranslationsParser(object):
    def __init__(self, transifex):
        self.transifex = transifex
        self.key_lang_str = '{}{}'.format(self.transifex.lang_prefix, self.transifex.key_lang)
        self.source_lang_str = '{}{}'.format(self.transifex.lang_prefix, self.transifex.source_lang)

    def _add_sheet(self, ws, po_entries):
        """
        :param ws: workbook sheet object
        :param po_entries: list of POEntry Objects to read translations from
        """
        sheet_name = ws.title
        if sheet_name == MODULES_AND_FORMS_SHEET_NAME:
            self._add_module_and_form_sheet(ws, po_entries)
        elif 'module' in sheet_name and 'form' not in sheet_name:
            self._add_module_sheet(ws, po_entries)
        elif 'module' in sheet_name and 'form' in sheet_name:
            self._add_form_sheet(ws, po_entries)
        else:
            self._add_generic_sheet(ws, po_entries)

    def _add_generic_sheet(self, ws, po_entries):
        # add header
        ws.append(["context", self.key_lang_str, self.source_lang_str])
        # add rows
        for po_entry in po_entries:
            ws.append([po_entry.msgctxt, po_entry.msgid, po_entry.msgstr])

    def _add_module_and_form_sheet(self, ws, po_entries):
        context_regex = CONTEXT_REGEXS['module_and_forms_sheet']
        # add header
        ws.append(["Type", "sheet_name", self.key_lang_str, self.source_lang_str, 'unique_id'])
        # add rows
        for po_entry in po_entries:
            context = po_entry.msgctxt
            _index, _type, _sheet_name, _unique_id = re.match(context_regex, context).groups()
            ws.append([_type, _sheet_name, po_entry.msgid, po_entry.msgstr, _unique_id])

    def _add_module_sheet(self, ws, po_entries):
        context_regex = CONTEXT_REGEXS['module_sheet']
        # add header
        ws.append(["case_property", "list_or_detail", self.key_lang_str, self.source_lang_str])
        # add rows
        for po_entry in po_entries:
            context = po_entry.msgctxt
            _index, _case_property, _list_or_detail = re.match(context_regex, context).groups()
            ws.append([_case_property, _list_or_detail, po_entry.msgid, po_entry.msgstr])

    def _add_form_sheet(self, ws, po_entries):
        context_regex = CONTEXT_REGEXS['form_sheet']
        # add header
        ws.append(["label", self.key_lang_str, self.source_lang_str])
        # add rows
        for po_entry in po_entries:
            context = po_entry.msgctxt
            _index, _label = re.match(context_regex, context).groups()
            ws.append([_label, po_entry.msgid, po_entry.msgstr])

    @memoized
    def _result_file_name(self):
        return ("TransifexTranslations {}-{}:v{} {}.xlsx".format(
            self.transifex.key_lang, self.transifex.source_lang,
            self.transifex.version, datetime.utcnow().strftime(DATETIME_FORMAT))
        )

    def _get_sheet_name(self, resource_name):
        return resource_name.split("_v%s" % self.transifex.version)[0]

    def _generate_sheets(self, wb):
        for resource_name, po_entries in self.transifex.get_translations().items():
            ws = wb.create_sheet(title=self._get_sheet_name(resource_name))
            self._add_sheet(ws, po_entries)

    def generate_excel_file(self):
        wb = Workbook(write_only=True)
        self._generate_sheets(wb)

        with NamedTemporaryFile(delete=False) as tempfile:
            wb.save(tempfile)
            return tempfile, self._result_file_name()
