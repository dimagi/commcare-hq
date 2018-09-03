from __future__ import absolute_import
from __future__ import unicode_literals
import os
import six
import sys

from django.utils.translation import ugettext as _
from django.conf import settings
from memoized import memoized

from corehq.apps.app_manager.app_translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.app_manager.app_translations.generators import TransifexPOFileGenerator
from corehq.apps.app_manager.app_translations.parser import TranslationsParser
from custom.icds.translations.integrations.client import TransifexApiClient


class Transifex(object):
    def __init__(self, domain, app_id, source_lang, project_slug, version=None, lang_prefix='default_',
                 resource_slugs=None, is_source_file=True, exclude_if_default=False, lock_translations=False,
                 use_version_postfix=True, update_resource=False):
        """
        :param domain: domain name
        :param app_id: id of the app to be used
        :param source_lang: source lang code like en or hin
        :param project_slug: project slug on transifex
        :param version: version of the app like 10475
        :param lang_prefix: prefix if other than "default_"
        :param resource_slugs: resource slugs
        :param is_source_file: upload as source language file(True) or translation(False)
        :param use_version_postfix: use version number at the end of resource slugs
        :param update_resource: update resource file
        """
        if version:
            version = int(version)
        self.version = version
        self.domain = domain
        self.key_lang = "en"  # the lang in which the string keys are, should be english
        self.lang_prefix = lang_prefix
        self.project_slug = project_slug
        self._resource_slugs = resource_slugs
        self.is_source_file = is_source_file
        self.source_lang = source_lang
        self.lock_translations = lock_translations
        self.use_version_postfix = use_version_postfix
        self.update_resource = update_resource
        self.transifex_po_file_generator = TransifexPOFileGenerator(domain, app_id, version, self.key_lang,
                                                                    source_lang, lang_prefix, exclude_if_default,
                                                                    use_version_postfix)

    def send_translation_files(self):
        """
        submit files to transifex for performing translations
        """
        try:
            self.transifex_po_file_generator.generate_translation_files()
            file_uploads = self._send_files_to_transifex()
        finally:
            self._cleanup()
        return file_uploads

    @property
    @memoized
    def client(self):
        transifex_account_details = settings.TRANSIFEX_DETAILS
        if transifex_account_details:
            return TransifexApiClient(
                transifex_account_details['token'],
                transifex_account_details['organization'],
                self.project_slug,
                self.use_version_postfix,
            )
        else:
            raise Exception(_("Transifex account details not available on this environment."))

    @property
    @memoized
    def transifex_project_source_lang(self):
        return self.client.transifex_lang_code(self.client.get_source_lang())

    def _resource_name_in_project_lang(self, resource_slug):
        """
        return the name of the resource i.e module/form in source lang on Transifex

        :param resource_slug: like module_moduleUniqueID
        """
        if MODULES_AND_FORMS_SHEET_NAME in resource_slug:
            return MODULES_AND_FORMS_SHEET_NAME
        module_or_form_unique_id = resource_slug.split('_')[1]
        resource_name_in_all_langs = self.transifex_po_file_generator.slug_to_name[module_or_form_unique_id]
        return resource_name_in_all_langs.get(self.transifex_project_source_lang,
                                              resource_name_in_all_langs.get('en', resource_slug))

    def _send_files_to_transifex(self):
        file_uploads = {}
        for resource_slug, path_to_file in self.transifex_po_file_generator.generated_files:
            resource_name = self._resource_name_in_project_lang(resource_slug)
            if self.is_source_file:
                response = self.client.upload_resource(
                    path_to_file,
                    resource_slug,
                    resource_name,
                    self.update_resource
                )
            else:
                response = self.client.upload_translation(
                    path_to_file, resource_slug,
                    resource_name, self.source_lang
                )
            if response.status_code in [200, 201]:
                file_uploads[resource_name] = _("Successfully Uploaded")
            else:
                file_uploads[resource_name] = "{}: {}".format(response.status_code, response.content)
        return file_uploads

    def _cleanup(self):
        self.transifex_po_file_generator.cleanup()

    @property
    @memoized
    def resource_slugs(self):
        if self._resource_slugs:
            return self._resource_slugs
        else:
            return self.client.get_resource_slugs(self.version)

    def _ensure_resources_belong_to_version(self):
        """
        confirms that resource slugs provided are for the expected version by checking for its name to end with
        v[version number] like v15 for version 15.
        """
        for resource_slug in self.resource_slugs:
            if not resource_slug.endswith("v%s" % self.version):
                raise Exception("Resource name '{}' is expected to contain version".format(
                    resource_slug
                ))

    def get_translations(self):
        """
        pull translations from transifex
        :return: dict of resource_slug mapped to POEntry objects
        """
        if self.version and self.use_version_postfix:
            self._ensure_resources_belong_to_version()
        po_entries = {}
        for resource_slug in self.resource_slugs:
            po_entries[resource_slug] = self.client.get_translation(resource_slug, self.source_lang,
                                                                    self.lock_translations)
        return po_entries

    def resources_pending_translations(self, break_if_true=False, all_langs=False):
        """
        :param break_if_true: break as soon as untranslated resource is found and return its slug/name
        :param all_langs: check for all langs for translation, if False just the source lang
        :return: single resource slug in case of break_if_true or a list of resources that are found
        with pending translations
        """
        resources_pending_translations = []
        check_for_lang = None if all_langs else self.source_lang
        for resource_slug in self.resource_slugs:
            if not self.client.translation_completed(resource_slug, check_for_lang):
                if break_if_true:
                    return resource_slug
                resources_pending_translations.append(resource_slug)
        return resources_pending_translations

    def generate_excel_file(self):
        parser = TranslationsParser(self)
        return parser.generate_excel_file()

    def source_lang_is(self, hq_lang_code):
        """
        confirm is source lang on transifex is same as hq lang code
        """
        return self.client.source_lang_is(hq_lang_code)

    def delete_resources(self):
        delete_status = {}
        for resource_slug in self.resource_slugs:
            response = self.client.delete_resource(resource_slug)
            if response.status_code == 204:
                delete_status[resource_slug] = _("Successfully Removed")
            else:
                delete_status[resource_slug] = response.content
        return delete_status
