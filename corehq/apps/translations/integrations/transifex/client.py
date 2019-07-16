from __future__ import absolute_import
from __future__ import unicode_literals

import json
import os
import tempfile
from io import open

import polib
import requests
from corehq.apps.translations.integrations.transifex.exceptions import (
    ResourceMissing,
    StringMissing,
    InvalidLockResourceRequest,
)
from memoized import memoized

from corehq.apps.translations.integrations.transifex.const import (
    API_USER,
    SOURCE_LANGUAGE_MAPPING,
)


class TransifexApiClient(object):
    def __init__(self, token, organization, project, use_version_postfix=True):
        self.username = API_USER
        self.token = token
        self.organization = organization
        self.project = project
        self.use_version_postfix = use_version_postfix

    @property
    def _auth(self):
        return self.username, self.token

    def list_resources(self):
        url = "https://api.transifex.com/organizations/{}/projects/{}/resources".format(
            self.organization,
            self.project
        )
        return requests.get(url, auth=self._auth)

    def get_resource_slugs(self, version):
        """
        :return: list of resource slugs corresponding to version
        """
        all_resources = self.list_resources().json()
        if version and self.use_version_postfix:
            # get all slugs with version postfix
            return [r['slug']
                    for r in all_resources
                    if r['slug'].endswith("v%s" % version)]
        elif version and not self.use_version_postfix:
            # get all slugs that don't have version postfix
            return [r['slug']
                    for r in all_resources
                    if not r['slug'].endswith("v%s" % version)]
        else:
            # get all slugs
            return [r['slug'] for r in all_resources]

    def update_resource_slug(self, old_resource_slug, new_resource_slug):
        url = "https://www.transifex.com/api/2/project/{}/resource/{}".format(
            self.project, old_resource_slug)
        data = {'slug': new_resource_slug}
        headers = {'content-type': 'application/json'}
        return requests.put(
            url, data=json.dumps(data), auth=self._auth, headers=headers,
        )

    def lock_resource(self, resource_slug):
        """
        lock a resource so that it can't be translated/reviewed anymore.

        :param resource_slug:
        """
        url = "https://www.transifex.com/api/2/project/{}/resource/{}".format(
            self.project, resource_slug)
        data = {
            'accept_translations': False
        }
        headers = {'content-type': 'application/json'}
        return requests.put(
            url, data=json.dumps(data), auth=self._auth, headers=headers,
        )

    def delete_resource(self, resource_slug):
        url = "https://www.transifex.com/api/2/project/{}/resource/{}".format(
            self.project, resource_slug)
        return requests.delete(url, auth=self._auth)

    def upload_resource(self, path_to_pofile, resource_slug, resource_name, update_resource):
        """
        Upload source language file

        :param path_to_pofile: path to pofile
        :param resource_slug: resource slug
        :param resource_name: resource name, mostly same as resource slug itself
        :param update_resource: update resource
        """
        content = open(path_to_pofile, 'r', encoding="utf-8").read()
        if resource_name is None:
            __, filename = os.path.split(path_to_pofile)
            resource_name = filename
        headers = {'content-type': 'application/json'}
        data = {
            'name': resource_name, 'slug': resource_slug, 'content': content,
            'i18n_type': 'PO'
        }
        if update_resource:
            url = "https://www.transifex.com/api/2/project/{}/resource/{}/content".format(
                self.project, resource_slug)
            return requests.put(
                url, data=json.dumps(data), auth=self._auth, headers=headers,
            )
        else:
            url = "https://www.transifex.com/api/2/project/{}/resources".format(self.project)
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
            self.project, resource_slug, target_lang_code)
        content = open(path_to_pofile, 'r', encoding="utf-8").read()
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
        response = requests.get(
            url, auth=self._auth,
        )
        if response.status_code == 404:
            raise ResourceMissing("Project not found with slug {}".format(self.project))
        else:
            return response

    @memoized
    def _resource_details(self, resource_slug):
        """
        get details for a resource corresponding to a lang

        :param resource_slug: resource slug
        """
        url = "https://www.transifex.com/api/2/project/{}/resource/{}/stats/".format(
            self.project, resource_slug)
        response = requests.get(url, auth=self._auth)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise ResourceMissing("Resource {} not found".format(resource_slug))
        raise Exception(response.content)

    def translation_completed(self, resource_slug, hq_lang_code=None):
        """
        check if a resource has been completely translated for
        all langs or a specific target lang
        """
        def completed(details):
            return not bool(details.get('untranslated_words'))

        if hq_lang_code:
            lang = self.transifex_lang_code(hq_lang_code)
            return completed(self._resource_details(resource_slug).get(lang, {}))
        else:
            for lang, detail in self._resource_details(resource_slug).items():
                if not completed(detail):
                    return False
            return True

    def get_translation(self, resource_slug, hq_lang_code, lock_resource=False, lock_reviewed=False):
        """
        get translations for a resource in the target lang.
        lock/freeze the resource if successfully pulled translations

        :param resource_slug: resource slug
        :param hq_lang_code: target lang code on HQ
        :param lock_resource: lock resource after pulling translation
        :param lock_reviewed: lock reviewed translations
        :return: list of POEntry objects
        """
        if lock_resource and lock_reviewed:
            raise InvalidLockResourceRequest("Unexpected request to lock both the resource and its translations")
        lang = self.transifex_lang_code(hq_lang_code)
        url = "https://www.transifex.com/api/2/project/{}/resource/{}/translation/{}/?file".format(
            self.project, resource_slug, lang
        )
        response = requests.get(url, auth=self._auth, stream=True)
        if response.status_code != 200:
            raise ResourceMissing
        temp_file = tempfile.NamedTemporaryFile()
        with open(temp_file.name, 'w', encoding='utf-8') as f:
            f.write(response.content.decode(encoding='utf-8'))
        if lock_resource:
            self.lock_resource(resource_slug)
        if lock_reviewed:
            self._lock_reviewed_strings_on_resource(resource_slug, hq_lang_code)
        return polib.pofile(temp_file.name)

    def _lock_reviewed_strings_on_resource(self, resource_slug, lang_code):
        """
        lock all strings on a resource, optionally only once that have been reviewed
        """
        lang_code = self.transifex_lang_code(lang_code)
        url = "https://www.transifex.com/api/2/project/{}/resource/{}/translation/{}/strings".format(
            self.project, resource_slug, lang_code)
        response = requests.get(url, auth=self._auth)
        for resource_detail in response.json():
            if resource_detail.get('reviewed'):
                self._lock_source_string_for_translation(resource_slug, lang_code, resource_detail['string_hash'])

    def _lock_source_string_for_translation(self, resource_slug, lang_code, string_hash):
        url = "https://www.transifex.com/api/2/project/{}/resource/{}/source/{}".format(
            self.project, resource_slug, string_hash)
        tags = self._get_string_details(url, resource_slug, string_hash)['tags']
        new_tag = "locked_%s" % self.transifex_lang_code(lang_code)
        tags = tags.append(new_tag) if tags else [new_tag]
        headers = {'content-type': 'application/json'}
        return requests.put(
            url, data=json.dumps({'tags': tags}), auth=self._auth, headers=headers,
        )

    def _get_string_details(self, url, resource_slug, string_hash):
        response = requests.get(url, auth=self._auth)
        if response.status_code == 200:
            return response.json()
        else:
            raise StringMissing("String with hash {} missing on resource {}".format(
                string_hash, resource_slug
            ))

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

    def move_resources(self, hq_lang_code, target_project, version=None, use_version_postfix=True):
        """
        ability to move resources from one project to another

        :param hq_lang_code: lang code on hq
        :param target_project: target project slug on transifex
        :param version: version if needed on parent resource slugs
        :param use_version_postfix: to use version postfix in new project
        :return: responses per resource slug
        """
        responses = {}
        for resource_slug in self.get_resource_slugs(version):
            lang = self.transifex_lang_code(hq_lang_code)
            url = "https://www.transifex.com/api/2/project/{}/resource/{}/translation/{}/?file".format(
                self.project, resource_slug, lang
            )
            response = requests.get(url, auth=self._auth, stream=True)
            if response.status_code != 200:
                raise ResourceMissing
            if use_version_postfix:
                upload_resource_slug = resource_slug
            else:
                upload_resource_slug = resource_slug.split("_v")[0]
            upload_url = "https://www.transifex.com/api/2/project/{}/resource/{}/translation/{}".format(
                target_project, upload_resource_slug, lang)
            content = response.content
            headers = {'content-type': 'application/json'}
            data = {
                'name': upload_resource_slug, 'slug': upload_resource_slug, 'content': content,
                'i18n_type': 'PO'
            }
            upload_response = requests.put(
                upload_url, data=json.dumps(data), auth=self._auth, headers=headers,
            )
            responses[resource_slug] = upload_response
        return responses
