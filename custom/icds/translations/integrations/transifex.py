from __future__ import absolute_import
from __future__ import unicode_literals
import os
import six
import sys

from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from corehq.apps.app_manager.app_translations.generators import POFileGenerator
from custom.icds.translations.integrations.client import TransifexApiClient


class Transifex:
    def __init__(self, domain, app_id, source_lang, project_slug, version=None, lang_prefix='default_'):
        """
        :param domain: domain name
        :param app_id: id of the app to be used
        :param source_lang: source lang code like en or hin
        :param project_slug: project slug on transifex
        :param version: version of the app like 10475
        :param lang_prefix: prefix if other than "default_"
        """
        if version:
            version = int(version)
        key_lang = "en"  # the lang in which the string keys are, should be english
        self.project_slug = project_slug
        self.po_file_generator = POFileGenerator(domain, app_id, version, key_lang, source_lang, lang_prefix)

    def send_translation_files(self):
        try:
            self.po_file_generator.generate_translation_files()
            self._send_files_to_transifex()
            self._cleanup()
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
        for filename in self.po_file_generator.generated_files:
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

    def _cleanup(self):
        for filename in self.po_file_generator.generated_files:
            if os.path.exists(filename):
                os.remove(filename)
