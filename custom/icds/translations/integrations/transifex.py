from __future__ import absolute_import
from __future__ import unicode_literals
import os
import six
import sys

from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from memoized import memoized

from corehq.apps.app_manager.app_translations.generators import POFileGenerator
from corehq.apps.app_manager.app_translations.parser import TranslationsParser
from custom.icds.translations.integrations.client import TransifexApiClient
from custom.icds.translations.integrations.const import SOURCE_LANGUAGE_MAPPING


class Transifex:
    def __init__(self, domain, app_id, source_lang, project_slug, version=None, lang_prefix='default_',
                 is_source_file=True, exclude_if_default=False):
        """
        :param domain: domain name
        :param app_id: id of the app to be used
        :param source_lang: source lang code like en or hin
        :param project_slug: project slug on transifex
        :param version: version of the app like 10475
        :param lang_prefix: prefix if other than "default_"
        :param is_source_file: upload as source language file(True) or translation(False)
        """
        if version:
            version = int(version)
        self.version = version
        self.key_lang = "en"  # the lang in which the string keys are, should be english
        self.lang_prefix = lang_prefix
        self.project_slug = project_slug
        self.is_source_file = is_source_file
        self.source_lang = source_lang
        self.po_file_generator = POFileGenerator(domain, app_id, version, self.key_lang, source_lang, lang_prefix,
                                                 exclude_if_default)
        self.parser = TranslationsParser(self)

    def send_translation_files(self):
        """
        submit files to transifex for performing translations
        :return:
        """
        try:
            self.po_file_generator.generate_translation_files()
            file_uploads = self._send_files_to_transifex()
            self._cleanup()
            return file_uploads
        except:
            t, v, tb = sys.exc_info()
            self._cleanup()
            six.reraise(t, v, tb)

    @memoized
    def client(self):
        transifex_account_details = settings.TRANSIFEX_DETAILS
        if transifex_account_details:
            return TransifexApiClient(
                transifex_account_details['token'],
                transifex_account_details['organization'],
                self.project_slug
            )
        else:
            raise Exception(_("Transifex account details not available on this environment."))

    def _send_files_to_transifex(self):
        file_uploads = {}
        client = self.client()
        for resource_name, path_to_file in self.po_file_generator.generated_files:
            if self.is_source_file:
                response = client.upload_resource(
                    path_to_file,
                    resource_name,
                    resource_name
                )
            else:
                lang_code = SOURCE_LANGUAGE_MAPPING.get(self.source_lang, self.source_lang)
                response = client.upload_translation(
                    path_to_file,
                    resource_name,
                    resource_name,
                    lang_code
                )
            if response.status_code in [200, 201]:
                file_uploads[resource_name] = _("Successfully Uploaded")
            else:
                file_uploads[resource_name] = "{}: {}".format(response.status_code, response.content)
        return file_uploads

    def _cleanup(self):
        for resource_name, filepath in self.po_file_generator.generated_files:
            if os.path.exists(filepath):
                os.remove(filepath)

    def _get_resource_slugs_for_version(self, version):
        """
        :param version: version number
        :return: list of resource slugs corresponding to version
        """
        return [r['name']
                for r in self.client().list_resources().json()
                if r['name'].endswith("v%s" % version)]

    @staticmethod
    def _ensure_resource_slugs_for_version(resource_slugs, version):
        """
        confirms that resource slugs provided are for the expected version by checking for its name to end with
        v[version number] like v15 for version 15.
        :param resource_slugs: list of resource slugs
        :param version: version
        """
        for resource_slug in resource_slugs:
            if not resource_slug.endswith("v%s" % version):
                raise Exception("Resource name '{}' is expected to contain version".format(
                    resource_slug
                ))

    def get_translations(self, resource_slugs=None):
        """
        pull translations from transifex
        :param resource_slugs: optional argument. All resource slugs corresponding to version are used otherwise.
        :return: list of POEntry objects
        """
        if resource_slugs:
            self._ensure_resource_slugs_for_version(resource_slugs, self.version)
        client = self.client()
        if not resource_slugs:
            resource_slugs = self._get_resource_slugs_for_version(self.version)
        if not resource_slugs:
            raise Exception("No resources found for this version")
        po_entries = {}
        for resource_slug in resource_slugs:
            po_entries[resource_slug] = client.get_translation(
                resource_slug,
                SOURCE_LANGUAGE_MAPPING.get(self.source_lang, self.source_lang)
            )
        return po_entries

    def resources_pending_translations(self, break_if_true=False):
        """
        :param break_if_true: break as soon as untranslated resource is found and return its slug/name
        :return: single resource slug in case of break_if_true or a list of resources that are found
        with pending translations
        """
        resource_slugs = self._get_resource_slugs_for_version(self.version)
        resources_pending_translations = []
        for resource_slug in resource_slugs:
            if not self.client().confirm_complete_translation(
                    resource_slug,
                    SOURCE_LANGUAGE_MAPPING.get(self.source_lang, self.source_lang)):
                if break_if_true:
                    return resource_slug
                resources_pending_translations.append(resource_slug)
        return resources_pending_translations
