from __future__ import absolute_import
from __future__ import unicode_literals
import requests
import os
import json
import tempfile
import polib

from custom.icds.translations.integrations.const import (
    API_USER,
    SOURCE_LANGUAGE_MAPPING,
)
from custom.icds.translations.integrations.exceptions import ResourceMissing


class TransifexApiClient():
    def __init__(self, token, organization, project):
        self.username = API_USER
        self.token = token
        self.organization = organization
        self.project = project

    @property
    def _auth(self):
        return self.username, self.token

    def list_resources(self):
        url = "https://api.transifex.com/organizations/{}/projects/{}/resources".format(
            self.organization,
            self.project
        )
        return requests.get(url, auth=self._auth)

    def delete_resource(self, resource_slug):
        url = "https://www.transifex.com/api/2/project/{}/resource/{}".format(
            self.project, resource_slug)
        return requests.delete(url, auth=self._auth)

    def upload_resource(self, path_to_pofile, resource_slug, resource_name):
        """
        Upload source language file
        :param path_to_pofile: path to pofile
        :param resource_slug: resource slug
        :param resource_name: resource name, mostly same as resource slug itself
        """
        url = "https://www.transifex.com/api/2/project/{}/resources".format(self.project)
        content = open(path_to_pofile, 'r').read()
        if resource_name is None:
            __, filename = os.path.split(path_to_pofile)
            resource_name = filename
        headers = {'content-type': 'application/json'}
        data = {
            'name': resource_name, 'slug': resource_slug, 'content': content,
            'i18n_type': 'PO'
        }
        return requests.post(
            url, data=json.dumps(data), auth=self._auth, headers=headers,
        )

    def upload_translation(self, path_to_pofile, resource_slug, resource_name, hq_lang_code):
        """
        Upload translated files
        :param path_to_pofile: path to pofile
        :param resource_slug: resource slug
        :param resource_name: resource name, mostly same as resource slug itself
        :param hq_lang_code: lang code on hq
        """
        target_lang_code = self.transifex_lang_code(hq_lang_code)
        url = "https://www.transifex.com/api/2/project/{}/resource/{}/translation/{}".format(
            self.project, resource_name, target_lang_code)
        content = open(path_to_pofile, 'r').read()
        headers = {'content-type': 'application/json'}
        data = {
            'name': resource_name, 'slug': resource_slug, 'content': content,
            'i18n_type': 'PO'
        }
        return requests.put(
            url, data=json.dumps(data), auth=self._auth, headers=headers,
        )

    def project_details(self):
        url = "https://www.transifex.com/api/2/project/{}/?details".format(self.project)
        return requests.get(
            url, auth=self._auth,
        )

    def _resource_details(self, resource_slug, lang):
        """
        get details for a resource corresponding to a lang
        :param resource_slug: resource slug
        :param lang: lang code on transifex
        """
        url = "https://www.transifex.com/api/2/project/{}/resource/{}/stats/{}".format(
            self.project, resource_slug, lang)
        response = requests.get(url, auth=self._auth)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise ResourceMissing("Resource {} not found for lang {}".format(resource_slug, lang))
        raise Exception(response.content)

    def translation_completed(self, resource_slug, hq_lang_code):
        """
        check if a resource has been completely translated for the target lang
        """
        lang = self.transifex_lang_code(hq_lang_code)
        return self._resource_details(resource_slug, lang)['completed'] == "100%"

    def get_translation(self, resource_slug, hq_lang_code):
        """
        get translations for a resource in the target lang
        :param resource_slug: resource slug
        :param hq_lang_code: target lang code on HQ
        :return: list of POEntry objects
        """
        lang = self.transifex_lang_code(hq_lang_code)
        url = "https://www.transifex.com/api/2/project/{}/resource/{}/translation/{}/?file".format(
            self.project, resource_slug, lang
        )
        response = requests.get(url, auth=self._auth, stream=True)
        if response.status_code != 200:
            return response
        temp_file = tempfile.NamedTemporaryFile()
        with open(temp_file.name, 'w') as f:
            f.write(response.content)
        return polib.pofile(temp_file.name)

    @staticmethod
    def transifex_lang_code(hq_lang_code):
        """
        Single place to convert lang codes from HQ to transifex lang code
        :param hq_lang_code: lang code on HQ
        """
        return SOURCE_LANGUAGE_MAPPING.get(hq_lang_code, hq_lang_code)

    def source_lang_is(self, hq_lang_code):
        """
        confirm is source lang on transifex is same as hq lang code
        """
        return self.transifex_lang_code(hq_lang_code) == self.get_source_lang()

    def get_source_lang(self):
        """
        :return: source lang code on transifex
        """
        return self.project_details().json().get('source_language_code')
