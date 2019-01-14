from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
import os
import re
import tempfile
from collections import namedtuple, OrderedDict, defaultdict

import polib
from django.utils.functional import cached_property
from memoized import memoized

from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.translations.models import TransifexBlacklist

Translation = namedtuple('Translation', 'key translation occurrences msgctxt')
Unique_ID = namedtuple('UniqueID', 'type id')
HQ_MODULE_SHEET_NAME = re.compile(r'^menu(\d+)$')
HQ_FORM_SHEET_NAME = re.compile(r'^menu(\d+)_form(\d+)$')
POFileInfo = namedtuple("POFileInfo", "name path")
SKIP_TRANSFEX_STRING = "SKIP TRANSIFEX"


class AppTranslationsGenerator(object):
    def __init__(self, domain, app_id, version, key_lang, source_lang, lang_prefix,
                 exclude_if_default=False, use_version_postfix=True):
        """
        Generates translations for source/default lang files and also for translated files
        :param domain: domain name
        :param app_id: app UUID
        :param version: version of the app to use, usually the built version. If none, the
        current app state is used.
        :param key_lang: the lang used to create msgid in PO files. Usually en.
        :param source_lang: the lang to create the msgstr in PO files. Should be same as
        key lang for source files and the target lang for translated files
        :param lang_prefix: usually default_
        :param exclude_if_default: set this to skip adding msgstr in case its same as the
        default language. For details: https://github.com/dimagi/commcare-hq/pull/20706
        :param use_version_postfix: use version number at the end of resource slugs
        """
        if key_lang == source_lang and exclude_if_default:
            raise Exception("Looks like you are setting up the file for default language "
                            "and doing that with exclude_if_default is not expected since "
                            "that would result in empty msgstr and no display for other lang")
        self.domain = domain
        self.app_id = app_id
        self.key_lang = key_lang
        self.source_lang = source_lang
        self.lang_prefix = lang_prefix
        self.exclude_if_default = exclude_if_default
        self.translations = OrderedDict()
        self.version = version
        self.use_version_postfix = use_version_postfix
        self.headers = dict()  # headers for each sheet name
        self.sheet_name_to_module_or_form_type_and_id = dict()
        self.slug_to_name = defaultdict(dict)
        self.slug_to_name[MODULES_AND_FORMS_SHEET_NAME] = {'en': MODULES_AND_FORMS_SHEET_NAME}
        self._build_translations()

    @cached_property
    def _get_labels_to_skip(self):
        """Returns the labels of questions that have the skip string in the comment,
        so that those labels are not sent to transifex later.

        If there are questions that share the same label reference (and thus the
        same translation), they will be included if any question does not have the
        skip string.
        """
        def _labels_from_question(question):
            ret = {
                question.get('label_ref'),
                question.get('constraintMsg_ref'),
            }
            if question.get('options'):
                for option in question['options']:
                    ret.add(option.get('label_ref'))
            return ret

        labels_to_skip = defaultdict(set)
        necessary_labels = defaultdict(set)

        for module in self.app.modules:
            for form in module.get_forms():
                questions = form.get_questions(self.app.langs, include_triggers=True,
                                               include_groups=True, include_translations=True)
                for question in questions:
                    if not question.get('label_ref'):
                        continue
                    if question['comment'] and SKIP_TRANSFEX_STRING in question['comment']:
                        labels_to_skip[form.unique_id] |= _labels_from_question(question)
                    else:
                        necessary_labels[form.unique_id] |= _labels_from_question(question)

        for form_id in labels_to_skip.keys():
            labels_to_skip[form_id] = labels_to_skip[form_id] - necessary_labels[form_id]

        return labels_to_skip

    def _translation_data(self, app):
        # get the translations data
        from corehq.apps.translations.app_translations.download import get_bulk_app_sheets_by_name
        # simply the rows of data per sheet name
        rows = get_bulk_app_sheets_by_name(
            app,
            exclude_module=lambda module: SKIP_TRANSFEX_STRING in module.comment,
            exclude_form=lambda form: SKIP_TRANSFEX_STRING in form.comment
        )

        # get the translation data headers
        from corehq.apps.translations.app_translations.utils import get_bulk_app_sheet_headers
        headers = get_bulk_app_sheet_headers(
            app,
            exclude_module=lambda module: SKIP_TRANSFEX_STRING in module.comment,
            exclude_form=lambda form: SKIP_TRANSFEX_STRING in form.comment
        )
        for header_row in headers:
            self.headers[header_row[0]] = header_row[1]
        self._set_sheet_name_to_module_or_form_mapping(rows[MODULES_AND_FORMS_SHEET_NAME])
        return rows

    def _set_sheet_name_to_module_or_form_mapping(self, all_module_and_form_details):
        # iterate the first sheet to get unique ids for forms/modules
        sheet_name_column_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'menu_or_form')
        unique_id_column_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'unique_id')
        type_column_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'Type')
        for row in all_module_and_form_details:
            self.sheet_name_to_module_or_form_type_and_id[row[sheet_name_column_index]] = Unique_ID(
                row[type_column_index],
                row[unique_id_column_index]
            )

    def _generate_module_sheet_name(self, module_index):
        """
        receive index of module and convert into name with module unique id

        :param module_index: index of module in the app
        :return: name like module_moduleUniqueId
        """
        _module = self.app.modules[module_index]
        sheet_name = "_".join(["module", _module.unique_id])
        self.slug_to_name[_module.unique_id] = _module.name
        return sheet_name

    def _generate_form_sheet_name(self, module_index, form_index):
        """
        receive index of form and module and convert into name with form unique id

        :param module_index: index of form's module in the app
        :param form_index: index of form in the module
        :return: name like form_formUniqueId
        """
        _module = self.app.modules[module_index]
        form = _module.forms[form_index]
        sheet_name = "_".join(["form", form.unique_id])
        self.slug_to_name[form.unique_id][self.source_lang] = "%s > %s" % (
            _module.name.get(self.source_lang, _module.default_name()),
            form.name.get(self.source_lang, form.default_name())
        )
        return sheet_name

    def _update_sheet_name_with_unique_id(self, sheet_name):
        """
        update sheet name with HQ format like menu0 or menu1_form1 to
        a name with unique id of module or form instead

        :param sheet_name: name like menu0 or menu1_form1
        :return: name like module_moduleUniqueID or form_formUniqueId
        """
        if sheet_name == MODULES_AND_FORMS_SHEET_NAME:
            return sheet_name
        module_sheet_name_match = HQ_MODULE_SHEET_NAME.match(sheet_name)
        if module_sheet_name_match:
            module_index = int(module_sheet_name_match.groups()[0]) - 1
            return self._generate_module_sheet_name(module_index)
        form_sheet_name_match = HQ_FORM_SHEET_NAME.match(sheet_name)
        if form_sheet_name_match:
            indexes = form_sheet_name_match.groups()
            module_index, form_index = int(indexes[0]) - 1, int(indexes[1]) - 1
            return self._generate_form_sheet_name(module_index, form_index)
        raise Exception("Got unexpected sheet name %s" % sheet_name)

    def _get_filename(self, sheet_name):
        """
        receive sheet name in HQ format and return the name that should be used
        to upload on transifex along with module/form unique ID and version postfix

        :param sheet_name: name like menu0 or menu1_form1
        :return: name like module_moduleUniqueID or form_formUniqueId
        """
        sheet_name = self._update_sheet_name_with_unique_id(sheet_name)
        if self.version and self.use_version_postfix:
            return sheet_name + '_v' + str(self.version)
        else:
            return sheet_name

    def _get_header_index(self, sheet_name, column_name):
        for index, _column_name in enumerate(self.headers[sheet_name]):
            if _column_name == column_name:
                return index
        raise Exception("Column not found with name {}".format(column_name))

    def _filter_invalid_rows_for_form(self, rows, form_id, label_index):
        """
        Remove translations from questions that have SKIP TRANSIFEX in the comment
        """
        labels_to_skip = self._get_labels_to_skip[form_id]
        valid_rows = []
        for i, row in enumerate(rows):
            question_label = row[label_index]
            if question_label not in labels_to_skip:
                valid_rows.append(row)
        return valid_rows

    @cached_property
    def _blacklisted_translations(self):
        return TransifexBlacklist.objects.filter(domain=self.domain, app_id=self.app_id).all()

    def _filter_invalid_rows_for_module(self, rows, module_id, case_property_index,
                                        list_or_detail_index, default_lang_index):
        valid_rows = []
        for i, row in enumerate(rows):
            list_or_detail = row[list_or_detail_index]
            case_property = row[case_property_index]
            default_lang = row[default_lang_index]
            in_blacklist = any(
                True
                for blacklisted_trans in self._blacklisted_translations
                if (
                    blacklisted_trans.module_id == module_id
                    and blacklisted_trans.field_type == list_or_detail
                    and blacklisted_trans.field_name == case_property
                    and (
                        blacklisted_trans.display_text == default_lang if blacklisted_trans.display_text else True
                    )
                )
            )
            if not in_blacklist:
                valid_rows.append(row)
        return valid_rows

    def _get_translation_for_sheet(self, app, sheet_name, rows):
        occurrence = None
        # a dict mapping of a context to a Translation object with
        # multiple occurrences
        translations = OrderedDict()
        type_and_id = None
        key_lang_index = self._get_header_index(sheet_name, self.lang_prefix + self.key_lang)
        source_lang_index = self._get_header_index(sheet_name, self.lang_prefix + self.source_lang)
        default_lang_index = self._get_header_index(sheet_name, self.lang_prefix + app.default_language)
        if sheet_name == MODULES_AND_FORMS_SHEET_NAME:
            type_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'Type')
            sheet_name_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'menu_or_form')
            unique_id_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'unique_id')

            def occurrence(_row):
                # keep legacy notation to use module to avoid expiring translations already present
                # caused by changing the context on the translation which is populated by this method
                return ':'.join(
                    [_row[type_index].replace("Menu", "Module"),
                     _row[sheet_name_index].replace("menu", "module"),
                     _row[unique_id_index]])
        else:
            type_and_id = self.sheet_name_to_module_or_form_type_and_id[sheet_name]
            if type_and_id.type == "Menu":
                case_property_index = self._get_header_index(sheet_name, 'case_property')
                list_or_detail_index = self._get_header_index(sheet_name, 'list_or_detail')
                rows = self._filter_invalid_rows_for_module(rows, type_and_id.id, case_property_index,
                                                            list_or_detail_index, default_lang_index)

                def occurrence(_row):
                    case_property = _row[case_property_index]
                    # limit case property length to avoid errors at Transifex where there is a limit of 1000
                    case_property = case_property[:950]
                    return ':'.join([case_property, _row[list_or_detail_index]])
            elif type_and_id.type == "Form":
                label_index = self._get_header_index(sheet_name, 'label')
                rows = self._filter_invalid_rows_for_form(rows, type_and_id.id, label_index)

                def occurrence(_row):
                    return _row[label_index]
        is_module = type_and_id and type_and_id.type == "Menu"
        for index, row in enumerate(rows, 1):
            source = row[key_lang_index]
            translation = row[source_lang_index]
            if self.exclude_if_default:
                if translation == row[default_lang_index]:
                    translation = ''
            occurrence_row = occurrence(row)
            occurrence_row_and_source = "%s %s" % (occurrence_row, source)
            if is_module:
                # if there is already a translation with the same context and source,
                # just add this occurrence
                if occurrence_row_and_source in translations:
                    translations[occurrence_row_and_source].occurrences.append(
                        ('', index)
                    )
                    continue

            translations[occurrence_row_and_source] = Translation(
                source,
                translation,
                [('', index)],
                occurrence_row)
        return list(translations.values())

    @property
    @memoized
    def app(self):
        from corehq.apps.app_manager.dbaccessors import get_current_app
        return get_current_app(self.domain, self.app_id)

    def _build_translations(self):
        """
        :return:
        {
            sheet_name_with_build_id: [
                Translation(key, translation, occurrences),
                Translation(key, translation, occurrences),
            ]
        }
        """
        app = self.app
        if self.version is None:
            self.version = app.version
        rows = self._translation_data(app)

        for sheet_name in rows:
            file_name = self._get_filename(sheet_name)
            self.translations[file_name] = self._get_translation_for_sheet(
                app, sheet_name, rows[sheet_name]
            )

    @property
    def metadata(self):
        now = str(datetime.datetime.now())
        return {
            'App-Id': self.app_id,
            'PO-Creation-Date': now,
            'MIME-Version': '1.0',
            'Content-Type': 'text/plain; charset=utf-8',
            'Language': self.key_lang,
            'Version': self.version
        }


class PoFileGenerator(object):
    def __init__(self, translations, metadata):
        self._generated_files = list()  # list of tuples (filename, filepath)
        self.translations = translations
        self.metadata = metadata

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self._cleanup()

    def generate_translation_files(self):
        for file_name in self.translations:
            sheet_translations = self.translations[file_name]
            po = polib.POFile()
            po.check_for_duplicates = False
            po.metadata = self.metadata
            for translation in sheet_translations:
                source = translation.key
                if source:
                    entry = polib.POEntry(
                        msgid=translation.key,
                        msgstr=translation.translation or '',
                        occurrences=translation.occurrences,
                        msgctxt=translation.msgctxt
                    )
                    po.append(entry)
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            po.save(temp_file.name)
            self._generated_files.append(POFileInfo(file_name, temp_file.name))
        return self._generated_files

    def _cleanup(self):
        for resource_name, filepath in self._generated_files:
            if os.path.exists(filepath):
                os.remove(filepath)
        self._generated_files = []
