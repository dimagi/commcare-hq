import re
from datetime import datetime

from openpyxl import Workbook

from corehq.apps.app_manager.app_translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.dump_reload.const import DATETIME_FORMAT


class TranslationsParser:
    def __init__(self, transifex):
        self.transifex = transifex
        self.translations = {}

    def _parse_module_and_form_sheet(self, ws, key_lang_str, source_lang_str, po_entries):
        regex = r'^(\d+):(Module|Form):(\w+):(\w+)$'
        ws.append(["Type", "sheet_name", key_lang_str, source_lang_str, 'unique_id'])
        for po_entry in po_entries:
            context = po_entry.msgctxt
            _index, _type, _sheet_name, _unique_id = re.match(regex, context).groups()
            ws.append([_type, _sheet_name, po_entry.msgid, po_entry.msgstr, _unique_id])
            self.translations[ws.title].append(
                {
                    'Type': _type,
                    'sheet_name': _sheet_name,
                    key_lang_str: po_entry.msgid,
                    source_lang_str: po_entry.msgstr,
                    'unique_id': _unique_id
                }
            )

    def _parse_module_sheet(self, ws, key_lang_str, source_lang_str, po_entries):
        regex = r'^(\d+):(.+):(list|detail)$'
        ws.append(["case_property", "list_or_detail", key_lang_str, source_lang_str])
        for po_entry in po_entries:
            context = po_entry.msgctxt
            _index, _case_property, _list_or_detail = re.match(regex, context).groups()
            ws.append([_case_property, _list_or_detail, po_entry.msgid, po_entry.msgstr])
            self.translations[ws.title].append(
                {
                    'case_property': _case_property,
                    'list_or_detail': _list_or_detail,
                    key_lang_str: po_entry.msgid,
                    source_lang_str: po_entry.msgstr
                }
            )

    def _parse_form_sheet(self, ws, key_lang_str, source_lang_str, po_entries):
        regex = r'^(\d+):(.+)$'
        ws.append(["label", key_lang_str, source_lang_str])
        for po_entry in po_entries:
            context = po_entry.msgctxt
            _index, _label = re.match(regex, context).groups()
            ws.append([_label, po_entry.msgid, po_entry.msgstr])
            self.translations[ws.title].append(
                {
                    'label': _label,
                    key_lang_str: po_entry.msgid,
                    source_lang_str: po_entry.msgstr
                }
            )

    def generate_excel_file(self, version, resource_slugs=None):
        wb = Workbook(write_only=True)
        key_lang_str = '{}{}'.format(self.transifex.lang_prefix, self.transifex.key_lang)
        source_lang_str = '{}{}'.format(self.transifex.lang_prefix, self.transifex.source_lang)
        all_translations = self.transifex.get_translations(version, resource_slugs)
        for resource_name in all_translations:
            po_entries = all_translations[resource_name]
            sheet_name = resource_name.split("_v%s" % version)[0]
            self.translations[sheet_name] = []
            if sheet_name == MODULES_AND_FORMS_SHEET_NAME:
                ws = wb.create_sheet(title=sheet_name)
                self._parse_module_and_form_sheet(ws, key_lang_str, source_lang_str, po_entries)
            elif 'module' in sheet_name and 'form' not in sheet_name:
                ws = wb.create_sheet(title=sheet_name)
                self._parse_module_sheet(ws, key_lang_str, source_lang_str, po_entries)
            elif 'module' in sheet_name and 'form' in sheet_name:
                ws = wb.create_sheet(title=sheet_name)
                self._parse_form_sheet(ws, key_lang_str, source_lang_str, po_entries)
            else:
                raise Exception("Got unexpected sheet name %s" % sheet_name)
        result_file_name = "TransifexTranslations {}-{}:v{} {}.xlsx".format(
            self.transifex.key_lang, self.transifex.source_lang,
            version, datetime.utcnow().strftime(DATETIME_FORMAT))
        wb.save(result_file_name)
