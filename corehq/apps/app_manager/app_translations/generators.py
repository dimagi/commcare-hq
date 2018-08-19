from __future__ import absolute_import
from __future__ import unicode_literals
import polib
import datetime
import tempfile

from django.conf import settings
from memoized import memoized

from collections import namedtuple, OrderedDict
from corehq.apps.app_manager.app_translations.const import MODULES_AND_FORMS_SHEET_NAME

Translation = namedtuple('Translation', 'key translation occurrences msgctxt')
Unique_ID = namedtuple('UniqueID', 'type id')


class POFileGenerator:
    def __init__(self, domain, app_id, version, key_lang, source_lang, lang_prefix,
                 exclude_if_default=False):
        """
        Generates PO files for source/default lang files and also for translated files
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
        self.headers = dict()  # headers for each sheet name
        self.generated_files = list()  # list of tuples (filename, filepath)
        self.sheet_name_to_module_or_form_type_and_id = dict()

    @property
    @memoized
    def app_id_to_build(self):
        return self._find_build_id()

    def _find_build_id(self):
        # find build id if version specified
        if self.version:
            from corehq.apps.app_manager.dbaccessors import get_all_built_app_ids_and_versions
            built_app_ids = get_all_built_app_ids_and_versions(self.domain, self.app_id)
            for app_built_version in built_app_ids:
                if app_built_version.version == self.version:
                    return app_built_version.build_id
            raise Exception("Build for version requested not found")
        else:
            return self.app_id

    def _translation_data(self, app):
        # get the translations data
        from corehq.apps.app_manager.app_translations.app_translations import expected_bulk_app_sheet_rows
        # simply the rows of data per sheet name
        rows = expected_bulk_app_sheet_rows(app)

        # get the translation data headers
        from corehq.apps.app_manager.app_translations.app_translations import expected_bulk_app_sheet_headers
        for header_row in expected_bulk_app_sheet_headers(app):
            self.headers[header_row[0]] = header_row[1]
        self._set_sheet_name_to_module_or_form_mapping(rows[MODULES_AND_FORMS_SHEET_NAME])
        return rows

    def _set_sheet_name_to_module_or_form_mapping(self, all_module_and_form_details):
        # iterate the first sheet to get unique ids for forms/modules
        sheet_name_column_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'sheet_name')
        unique_id_column_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'unique_id')
        type_column_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'Type')
        for row in all_module_and_form_details:
            self.sheet_name_to_module_or_form_type_and_id[row[sheet_name_column_index]] = Unique_ID(
                row[type_column_index],
                row[unique_id_column_index]
            )

    def _get_filename(self, sheet_name):
        if self.version:
            return sheet_name + '_v' + str(self.version)
        else:
            return sheet_name

    def _get_header_index(self, sheet_name, column_name):
        for index, _column_name in enumerate(self.headers[sheet_name]):
            if _column_name == column_name:
                return index
        raise Exception("Column not found with name {}".format(column_name))

    def _get_translation_for_sheet(self, app, sheet_name, rows):
        occurrence = None
        translations_for_sheet = []
        key_lang_index = self._get_header_index(sheet_name, self.lang_prefix + self.key_lang)
        source_lang_index = self._get_header_index(sheet_name, self.lang_prefix + self.source_lang)
        default_lang_index = self._get_header_index(sheet_name, self.lang_prefix + app.default_language)
        if sheet_name == MODULES_AND_FORMS_SHEET_NAME:
            type_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'Type')
            sheet_name_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'sheet_name')
            unique_id_index = self._get_header_index(MODULES_AND_FORMS_SHEET_NAME, 'unique_id')

            def occurrence(_row):
                return ':'.join([_row[type_index], _row[sheet_name_index], _row[unique_id_index]])
        else:
            type_and_id = self.sheet_name_to_module_or_form_type_and_id[sheet_name]
            if type_and_id.type == "Module":
                case_property_index = self._get_header_index(sheet_name, 'case_property')
                list_or_detail_index = self._get_header_index(sheet_name, 'list_or_detail')

                def occurrence(_row):
                    case_property = _row[case_property_index]
                    # limit case property length to avoid errors at Transifex where there is a limit of 1000
                    case_property = case_property[:950]
                    return ':'.join([case_property, _row[list_or_detail_index]])
            elif type_and_id.type == "Form":
                label_index = self._get_header_index(sheet_name, 'label')

                def occurrence(_row):
                    return _row[label_index]
        for i, row in enumerate(rows):
            source = row[key_lang_index]
            translation = row[source_lang_index]
            if self.exclude_if_default:
                if translation == row[default_lang_index]:
                    translation = ''
            occurrence_row = occurrence(row)
            translations_for_sheet.append(Translation(
                source,
                translation,
                [(occurrence_row, '')],
                ':'.join([str(i), occurrence_row]))
            )
        return translations_for_sheet

    def _build_translations(self):
        """
        :return:
        {
            sheet_name_with_build_id: {
                key: Translation(key, translation, occurrences)
            }
        }
        """
        from corehq.apps.app_manager.dbaccessors import get_current_app
        app = get_current_app(self.domain, self.app_id_to_build)

        rows = self._translation_data(app)

        for sheet_name in rows:
            file_name = self._get_filename(sheet_name)
            self.translations[file_name] = self._get_translation_for_sheet(
                app, sheet_name, rows[sheet_name]
            )

    def generate_translation_files(self):
        self._build_translations()
        if settings.TRANSIFEX_DETAILS:
            team = settings.TRANSIFEX_DETAILS['teams'][self.domain].get(self.source_lang)
        else:
            team = ""
        now = str(datetime.datetime.now())
        for file_name in self.translations:
            sheet_translations = self.translations[file_name]
            po = polib.POFile()
            po.check_for_duplicates = False
            po.metadata = {
                'App-Id': self.app_id_to_build,
                'PO-Creation-Date': now,
                'Language-Team': "{lang} ({team})".format(
                    lang=self.key_lang, team=team
                ),
                'MIME-Version': '1.0',
                'Content-Type': 'text/plain; charset=utf-8',
                'Content-Transfer-Encoding': '8bit',
                'Language': self.key_lang,
                'Version': self.version
            }

            for translation in sheet_translations:
                source = translation.key
                if source:
                    entry = polib.POEntry(
                        msgid=translation.key,
                        msgstr=translation.translation,
                        occurrences=translation.occurrences,
                        msgctxt=translation.msgctxt
                    )
                    po.append(entry)
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            po.save(temp_file.name)
            self.generated_files.append((file_name, temp_file.name))
