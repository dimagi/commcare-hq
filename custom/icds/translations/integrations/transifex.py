from __future__ import absolute_import
from __future__ import unicode_literals
import polib
import datetime
import os

from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from collections import namedtuple, OrderedDict
from corehq.apps.app_manager import id_strings
from custom.icds.translations.integrations.client import TransifexApiClient

Translation = namedtuple('Translation', 'key translation occurrences')
Unique_ID = namedtuple('UniqueID', 'type id')


class Transifex():
    def __init__(self, domain, app_id, source_lang, project_slug, version=None, lang_prefix='default_'):
        """
        :param domain: domain name
        :param app_id: id of the app to be used
        :param source_lang: source lang code like en or hin
        :param project_slug: project slug on transifex
        :param version: version of the app like 10475
        :param lang_prefix: prefix if other than "default_"
        """
        self.app_id = app_id
        self.domain = domain
        if version:
            self.version = int(version)
        else:
            self.version = None
        self.key_lang = "en"  # the lang in which the string keys are, should be english
        self.source_lang = source_lang
        self.project_slug = project_slug
        self.lang_prefix = lang_prefix
        self.app_id_to_build = None
        self.translations = OrderedDict()
        self.headers = dict()  # headers for each sheet name
        self.sheet_name_to_module_or_form_type_and_id = dict()
        self.generated_files = list()

    def _find_build_id(self):
        # find build id if version specified
        if self.version:
            from corehq.apps.app_manager.dbaccessors import get_all_built_app_ids_and_versions
            built_app_ids = get_all_built_app_ids_and_versions(self.domain, self.app_id)
            for app_built_version in built_app_ids:
                if app_built_version.version == self.version:
                    self.app_id_to_build = app_built_version.build_id
                    break
            if not self.app_id_to_build:
                raise Exception("Build for version requested not found")
        else:
            self.app_id_to_build = self.app_id

    def _translation_data(self, app):
        # get the translations data
        from corehq.apps.app_manager.app_translations.app_translations import expected_bulk_app_sheet_rows
        # simply the rows of data per sheet name
        rows = expected_bulk_app_sheet_rows(app)

        # get the translation data headers
        from corehq.apps.app_manager.app_translations.app_translations import expected_bulk_app_sheet_headers
        for header_row in expected_bulk_app_sheet_headers(app):
            self.headers[header_row[0]] = header_row[1]
        self._set_sheet_name_to_module_or_form_mapping(rows[u'Modules_and_forms'])
        return rows

    def _set_sheet_name_to_module_or_form_mapping(self, all_module_and_form_details):
        # iterate the first sheet to get unique ids for forms/modules
        sheet_name_column_index = self._get_header_index(u'Modules_and_forms', 'sheet_name')
        unique_id_column_index = self._get_header_index(u'Modules_and_forms', 'unique_id')
        type_column_index = self._get_header_index(u'Modules_and_forms', 'Type')
        for row in all_module_and_form_details:
            self.sheet_name_to_module_or_form_type_and_id[row[sheet_name_column_index]] = Unique_ID(
                row[type_column_index],
                row[unique_id_column_index]
            )

    def _get_filename(self, sheet_name):
        return sheet_name + '_v' + str(self.version)

    def _get_header_index(self, sheet_name, column_name):
        for index, _column_name in enumerate(self.headers[sheet_name]):
            if _column_name == column_name:
                return index
        raise Exception("Column not found with name {}".format(column_name))

    def _get_translation_for_sheet(self, app, sheet_name, rows):
        translations_for_sheet = OrderedDict()
        key_lang_index = self._get_header_index(sheet_name, self.lang_prefix + self.key_lang)
        source_lang_index = self._get_header_index(sheet_name, self.lang_prefix + self.source_lang)
        occurrences = []
        if sheet_name != u'Modules_and_forms':
            type_and_id = self.sheet_name_to_module_or_form_type_and_id[sheet_name]
            if type_and_id.type == "Module":
                ref_module = app.get_module_by_unique_id(type_and_id.id)
                occurrences = [(id_strings.module_locale(ref_module), '')]
            elif type_and_id.type == "Form":
                ref_form = app.get_form(type_and_id.id)
                occurrences = [(id_strings.form_locale(ref_form), '')]
        for row in rows:
            source = row[key_lang_index]
            translation = row[source_lang_index]
            if source not in translations_for_sheet:
                translations_for_sheet[source] = Translation(
                    source,
                    translation or source,  # to avoid blank msgstr in po file
                    [].extend(occurrences))
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
        # get app or the app for the build
        self._find_build_id()
        from corehq.apps.app_manager.dbaccessors import get_app
        app = get_app(self.domain, self.app_id_to_build)
        if self.version is None:
            self.version = app.version

        rows = self._translation_data(app)

        for sheet_name in rows:
            file_name = self._get_filename(sheet_name)
            self.translations[file_name] = self._get_translation_for_sheet(
                app, sheet_name, rows[sheet_name]
            )

    def _store_translations_to_po_files(self):
        if settings.TRANSIFEX_DETAILS:
            team = settings.TRANSIFEX_DETAILS['teams'].get(self.key_lang)
        else:
            team = ""
        now = str(datetime.datetime.now())
        for file_name in self.translations:
            sheet_translations = self.translations[file_name]
            po = polib.POFile()
            po.check_for_duplicates = True
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

            for source in sheet_translations:
                if source:
                    translation = sheet_translations[source]
                    entry = polib.POEntry(
                        msgid=translation.key,
                        msgstr=translation.translation,
                        occurrences=translation.occurrences
                    )
                    po.append(entry)
            po.save(file_name)
            self.generated_files.append(file_name)

    def send_translation_files(self):
        self._build_translations()
        self._store_translations_to_po_files()
        self._send_files_to_transifex()
        self._cleanup()

    def _send_files_to_transifex(self):
        transifex_account_details = settings.TRANSIFEX_DETAILS
        if transifex_account_details:
            file_uploads = {}
            client = TransifexApiClient(
                transifex_account_details['token'],
                transifex_account_details['organization'],
                self.project_slug
            )
            for filename in self.generated_files:
                response = client.upload_resource(
                    filename,
                    filename,
                    filename
                )
                if response.status_code == 201:
                    file_uploads[filename] = _("Successfully Uploaded")
                else:
                    file_uploads[filename] = "{}: {}".format(response.status_code, response.content)
            return file_uploads
        else:
            raise Exception(_("Transifex account details not available on this environment."))

    def _cleanup(self):
        for filename in self.generated_files:
            os.remove(filename)
