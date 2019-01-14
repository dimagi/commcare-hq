from __future__ import absolute_import
from __future__ import unicode_literals

import re
from datetime import datetime
from openpyxl import Workbook
from tempfile import NamedTemporaryFile
from memoized import memoized

from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.dump_reload.const import DATETIME_FORMAT


CONTEXT_REGEXS = {
    # Module or Form: sheet name for module/form: unique id
    'module_and_forms_sheet': r'^(Module|Form):(\w+):(\w+)$',  # maintain legacy module usage instead of menu
    # case property: list/detail
    'module_sheet': r'^(.+):(list|detail)$',
}

TRANSIFEX_MODULE_RESOURCE_NAME = re.compile(r'^module_(\w+)(_v\d+)?$')  # module_moduleUniqueID_v123
TRANSIFEX_FORM_RESOURCE_NAME = re.compile(r'^form_(\w+)(_v\d+)?$')  # form_formUniqueID_v123


class TranslationsParser(object):
    def __init__(self, transifex):
        self.transifex = transifex
        self.key_lang_str = '{}{}'.format(self.transifex.lang_prefix, self.transifex.key_lang)
        self.source_lang_str = '{}{}'.format(self.transifex.lang_prefix, self.transifex.source_lang)

    @property
    @memoized
    def get_app(self):
        from corehq.apps.app_manager.dbaccessors import get_current_app
        try:
            app_build_id = self.transifex.app_id_to_build
        except AttributeError:
            app_build_id = self.transifex.app_id
        return get_current_app(self.transifex.domain, app_build_id)

    def _add_sheet(self, ws, po_entries):
        """
        :param ws: workbook sheet object
        :param po_entries: list of POEntry Objects to read translations from
        """
        sheet_name = ws.title
        if sheet_name == MODULES_AND_FORMS_SHEET_NAME:
            self._add_module_and_form_sheet(ws, po_entries)
        elif 'menu' in sheet_name and 'form' not in sheet_name:
            self._add_module_sheet(ws, po_entries)
        elif 'menu' in sheet_name and 'form' in sheet_name:
            self._add_form_sheet(ws, po_entries)
        else:
            raise Exception("Got unexpected sheet name %s" % sheet_name)

    def _add_module_and_form_sheet(self, ws, po_entries):
        context_regex = CONTEXT_REGEXS['module_and_forms_sheet']
        # add header
        ws.append(["Type", "menu_or_form", self.key_lang_str, self.source_lang_str, 'unique_id'])
        # add rows
        for po_entry in po_entries:
            context = po_entry.msgctxt
            _type, _sheet_name, _unique_id = re.match(context_regex, context).groups()
            # replace the legacy module notation with new menu notation
            ws.append([_type.replace('Module', 'Menu'),
                       _sheet_name.replace('module', 'menu'),
                       po_entry.msgid, po_entry.msgstr, _unique_id])

    @staticmethod
    def _get_rows_for_module_sheet(consolidated_po_entries):
        """
        get po_entries listed according to their expected order in the final set
        by using occurrences
        """
        rows = {}
        # align entries in a dict with their index as the key
        for po_entry in consolidated_po_entries:
            occurrences = po_entry.occurrences
            for occurrence in occurrences:
                index = int(occurrence[1])
                rows[index] = po_entry
        # ensure the number of final translations is same as the highest index
        # if rows:
            # ToDo: Add this message
            # if len(rows) != int(max(rows.keys())):
                # add a message for the user
        # sort by index to have the expected order
        return [po_entry for i, po_entry in sorted(rows.items())]

    def _add_module_sheet(self, ws, po_entries):
        context_regex = CONTEXT_REGEXS['module_sheet']
        # add header
        ws.append(["case_property", "list_or_detail", self.key_lang_str, self.source_lang_str])
        for po_entry in self._get_rows_for_module_sheet(po_entries):
            context = po_entry.msgctxt
            _case_property, _list_or_detail = re.match(context_regex, context).groups()
            ws.append([_case_property, _list_or_detail, po_entry.msgid, po_entry.msgstr])

    def _add_form_sheet(self, ws, po_entries):
        # add header
        ws.append(["label", self.key_lang_str, self.source_lang_str])
        # add rows
        for po_entry in po_entries:
            _label = po_entry.msgctxt
            ws.append([_label, po_entry.msgid, po_entry.msgstr])

    @memoized
    def _result_file_name(self):
        return ("TransifexTranslations {}-{}:v{} {}.xlsx".format(
            self.transifex.key_lang, self.transifex.source_lang,
            self.transifex.version, datetime.utcnow().strftime(DATETIME_FORMAT))
        )

    def _generate_form_sheet_name(self, form_unique_id):
        """
        receive a form unique id and convert into name with module and form index
        as expected by HQ

        :param form_unique_id:
        :return:
        """
        form = self.get_app.get_form(form_unique_id)
        _module = form.get_module()
        module_index = self.get_app.get_module_index(_module.unique_id) + 1
        form_index = _module.get_form_index(form_unique_id) + 1
        return "menu%s_form%s" % (module_index, form_index)

    def _get_sheet_name_with_indexes(self, resource_slug):
        """
        receives resource slug from transifex trimmed of version postfix and update to
        sheet name with module/form indexes as expected by HQ

        :param resource_slug: name like module_moduleUniqueID or form_formUniqueID
        :return: name like module1 or module1_form1
        """
        if resource_slug == MODULES_AND_FORMS_SHEET_NAME:
            return resource_slug
        module_sheet_name_match = TRANSIFEX_MODULE_RESOURCE_NAME.match(resource_slug)
        if module_sheet_name_match:
            module_unique_id = module_sheet_name_match.groups()[0]
            module_index = self.get_app.get_module_index(module_unique_id) + 1
            return "menu%s" % module_index
        form_sheet_name_match = TRANSIFEX_FORM_RESOURCE_NAME.match(resource_slug)
        if form_sheet_name_match:
            form_unique_id = form_sheet_name_match.groups()[0]
            return self._generate_form_sheet_name(form_unique_id)
        raise Exception("Got unexpected sheet name %s" % resource_slug)

    def _get_sheet_name(self, resource_slug):
        """
        receives resource slug and converts to excel sheet name as expected by HQ

        :param resource_slug: like module_moduleUniqueID_v15 or form_formUniqueID
        :return: name like menu1 or menu1_form1
        """
        resource_slug = resource_slug.split("_v%s" % self.transifex.version)[0]
        return self._get_sheet_name_with_indexes(resource_slug)

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
