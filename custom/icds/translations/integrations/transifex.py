from __future__ import absolute_import
from __future__ import unicode_literals
import os
import six
import sys

from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from corehq.apps.app_manager.app_translations.generators import POFileGenerator
from custom.icds.translations.integrations.client import TransifexApiClient
from custom.icds.translations.integrations.const import SOURCE_LANGUAGE_MAPPING


class Transifex:
    def __init__(self, domain, app_id, source_lang, project_slug, version=None, lang_prefix='default_',
                 is_source_file=True):
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
        key_lang = "en"  # the lang in which the string keys are, should be english
        self.project_slug = project_slug
        self.is_source_file = is_source_file
        self.source_lang = source_lang
        self.po_file_generator = POFileGenerator(domain, app_id, version, key_lang, source_lang, lang_prefix)

    def send_translation_files(self):
        try:
            self.po_file_generator.generate_translation_files()
            file_uploads = self._send_files_to_transifex()
            self._cleanup()
            return file_uploads
        except:
            t, v, tb = sys.exc_info()
            self._cleanup()
            six.reraise(t, v, tb)

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
        for _, filepath in self.po_file_generator.generated_files:
            if os.path.exists(filepath):
                os.remove(filepath)
