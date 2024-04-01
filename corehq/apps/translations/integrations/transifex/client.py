import json
import os
import tempfile

import polib
import requests
from memoized import memoized

from corehq.apps.translations.integrations.transifex.const import (
    API_USER,
    SOURCE_LANGUAGE_MAPPING,
)
from corehq.apps.translations.integrations.transifex.exceptions import (
    ResourceMissing,
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

    def _create_resource(self, resource_slug, resource_name):
        ...

    def _upload_resource_strings(self, content, resource_id):
        ...

    def _upload_resource_translations(self, content, resource_id, language_id):
        ...

    def _get_project(self, project_slug):
        ...

    def _get_resource(self, resource_slug):
        ...

    def _list_resources(self):
        ...

    def _download_resource_translations(self, resource_id, language_id):
        ...

    def _lock_resource(self, resource):
        ...

    def delete_resource(self, resource_slug):
        ...

    def list_resources(self):
        return self._list_resources()

    def get_resource_slugs(self, version):
        """
        :return: list of resource slugs corresponding to version
        """
        all_resources = self._list_resources().json()
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
        # slug is immutable from Transifex API v3
        pass

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
        if update_resource:
            resource = self._get_resource(resource_slug)
        else:
            resource = self._create_resource(resource_slug, resource_name)
        self._upload_resource_strings(content, resource.id)

    def upload_translation(self, path_to_pofile, resource_slug, resource_name, hq_lang_code):
        """
        Upload translated files

        :param path_to_pofile: path to pofile
        :param resource_slug: resource slug
        :param resource_name: resource name, mostly same as resource slug itself
        :param hq_lang_code: lang code on hq
        """
        target_lang_code = self.transifex_lang_code(hq_lang_code)
        content = open(path_to_pofile, 'r', encoding="utf-8").read()
        resource = self._get_resource(resource_slug)
        self._upload_resource_translations(content, resource.id, target_lang_code)

    def project_details(self):
        return self.project

    @memoized
    def _resource_details(self, resource_slug):
        """
        get details for a resource corresponding to a lang

        :param resource_slug: resource slug
        """
        return self._get_resource(resource_slug)

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

    def get_translation(self, resource_slug, hq_lang_code, lock_resource):
        """
        get translations for a resource in the target lang.
        lock/freeze the resource if successfully pulled translations

        :param resource_slug: resource slug
        :param hq_lang_code: target lang code on HQ
        :param lock_resource: lock resource after pulling translation
        :return: list of POEntry objects
        """
        resource = self._get_resource(resource_slug)
        lang = self.transifex_lang_code(hq_lang_code)
        content = self._download_resource_translations(resource.id, lang)
        temp_file = tempfile.NamedTemporaryFile()
        with open(temp_file.name, 'w', encoding='utf-8') as f:
            f.write(content.decode(encoding='utf-8'))
        if lock_resource:
            self._lock_resource(resource_slug)
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

    def move_resources(self, hq_lang_code, target_project, version=None, use_version_postfix=True):
        # not exposed to UI
        pass
