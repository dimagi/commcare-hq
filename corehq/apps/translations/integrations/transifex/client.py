import json
import os
import tempfile

import polib
import requests
from transifex.api import TransifexApi
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
        self.use_version_postfix = use_version_postfix
        self.api = TransifexApi(auth=token)
        self.organization = self._get_organization(organization)
        self.project = self._get_project(project)

    @property
    def _i18n_format(self):
        return self.api.I18nFormat(id="PO")

    @property
    def project_name(self):
        return self.project.name

    @property
    def source_language_id(self):
        return self.project.source_language.id

    @property
    def source_lang_code(self):
        return self._to_lang_code(self.source_language_id)

    def _create_resource(self, resource_slug, resource_name):
        return self.api.Resource.create(
            name=resource_name,
            slug=resource_slug,
            project=self.project,
            i18n_format=self._i18n_format
        )

    @staticmethod
    def _upload_content(cls, content, **kwargs):
        # TransifexApi.upload() waits for async upload which we don't need, so create the upload manually
        cls.create_with_form(data=kwargs, files={"content": content})

    def _upload_resource_strings(self, content, resource_id):
        cls = self.api.ResourceStringsAsyncUpload
        self._upload_content(cls, content, resource=resource_id)

    def _upload_resource_translations(self, content, resource_id, language_id):
        cls = self.api.ResourceTranslationsAsyncUpload
        self._upload_content(cls, content, resource=resource_id, language=language_id)

    @staticmethod
    def _get_object(cls, **kwargs):
        return cls.get(**kwargs)

    def _get_organization(self, organization_slug):
        cls = self.api.Organization
        return self._get_object(cls, slug=organization_slug)

    def _get_project(self, project_slug):
        cls = self.api.Project
        return self._get_object(cls, slug=project_slug, organization=self.organization)

    def _get_resource(self, resource_slug):
        cls = self.api.Resource
        return self._get_object(cls, slug=resource_slug, project=self.project)

    def _get_language_stats(self, resource_id, language_id):
        cls = self.api.ResourceLanguageStats
        return self._get_object(cls, id=language_id, resource=resource_id)

    @staticmethod
    def _list_objects(cls, **kwargs):
        return cls.filter(**kwargs)

    def _list_resources(self):
        cls = self.api.Resource
        return self._list_objects(cls, project=self.project)

    def _list_language_stats(self, **kwargs):
        cls = self.api.ResourceLanguageStats
        return self._list_objects(cls, project=self.project, **kwargs)

    def _fetch_related(self, obj, key):
        return obj.fetch(key)

    @staticmethod
    def _download_content(cls, **kwargs):
        download = cls.download(**kwargs)
        response = requests.get(download, stream=True)
        return response.content

    def _download_resource_translations(self, resource_id, language_id):
        cls = self.api.ResourceTranslationsAsyncDownload
        return self._download_content(cls, resource=resource_id, language_id=language_id)

    def _lock_resource(self, resource):
        return resource.save(accept_translations=False)

    def delete_resource(self, resource_slug):
        resource = self._get_resource(resource_slug)
        resource.delete()

    def list_resources(self):
        return self._list_resources()

    def get_resource_slugs(self, version):
        """
        :return: list of resource slugs corresponding to version
        """
        all_resources = self._list_resources()
        if version and self.use_version_postfix:
            # get all slugs with version postfix
            return [r.slug
                    for r in all_resources
                    if r.slug.endswith("v%s" % version)]
        elif version and not self.use_version_postfix:
            # get all slugs that don't have version postfix
            return [r.slug
                    for r in all_resources
                    if not r.slug.endswith("v%s" % version)]
        else:
            # get all slugs
            return [r.slug for r in all_resources]

    def update_resource_slug(self, old_resource_slug, new_resource_slug):
        # slug is immutable from Transifex API v3
        pass

    def upload_resource(self, path_to_po_file, resource_slug, resource_name, update_resource):
        """
        Upload source language file

        :param path_to_po_file: path to po file
        :param resource_slug: resource slug
        :param resource_name: resource name, mostly same as resource slug itself
        :param update_resource: update resource
        """
        if update_resource:
            resource = self._get_resource(resource_slug)
        else:
            # must create the new resource first
            if resource_name is None:
                __, filename = os.path.split(path_to_po_file)
                resource_name = filename
            resource = self._create_resource(resource_slug, resource_name)
        with open(path_to_po_file, 'r', encoding="utf-8") as po_file:
            content = po_file.read()
        self._upload_resource_strings(content, resource.id)

    def upload_translation(self, path_to_po_file, resource_slug, hq_lang_code):
        """
        Upload translated files

        :param path_to_po_file: path to po file
        :param resource_slug: resource slug
        :param hq_lang_code: lang code on hq
        """
        language_id = self._to_language_id(self.transifex_lang_code(hq_lang_code))
        resource = self._get_resource(resource_slug)
        with open(path_to_po_file, 'r', encoding="utf-8") as po_file:
            content = po_file.read()
        self._upload_resource_translations(content, resource.id, language_id)

    @memoized
    def _resource_details(self, resource_slug):
        """
        get details for a resource corresponding to a lang

        :param resource_slug: resource slug
        """
        return self._get_resource(resource_slug)

    def is_translation_completed(self, resource_slug, hq_lang_code=None):
        """
        check if a resource has been completely translated for
        all langs or a specific target lang
        """
        def completed(stats):
            return not bool(stats.untranslated_words)

        resource = self._get_resource(resource_slug)
        if hq_lang_code:
            language_id = self._to_language_id(self.transifex_lang_code(hq_lang_code))
            language_stats = self._get_language_stats(resource.id, language_id)
            return completed(language_stats)
        else:
            language_stats_list = self._list_language_stats(resource_id=resource.id)
            return all(completed(stats) for stats in language_stats_list)

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
        language_id = self._to_language_id(self.transifex_lang_code(hq_lang_code))
        content = self._download_resource_translations(resource.id, language_id)
        temp_file = tempfile.NamedTemporaryFile()
        with open(temp_file.name, 'w', encoding='utf-8') as f:
            f.write(content.decode(encoding='utf-8'))
        if lock_resource:
            self._lock_resource(resource)
        return polib.pofile(temp_file.name)

    @staticmethod
    def transifex_lang_code(hq_lang_code):
        """
        Single place to convert lang codes from HQ to transifex lang code

        :param hq_lang_code: lang code on HQ
        """
        return SOURCE_LANGUAGE_MAPPING.get(hq_lang_code, hq_lang_code)

    def get_project_langcodes(self):
        languages = self._fetch_related(self.project, 'languages')
        languages.append(self.project.source_language)
        return [self._to_lang_code(language.id) for language in languages]

    def source_lang_is(self, hq_lang_code):
        """
        confirm is source lang on transifex is same as hq lang code
        """
        return self.transifex_lang_code(hq_lang_code) == self.source_lang_code

    def get_source_lang(self):
        """
        :return: source lang code on transifex
        """
        return self._to_lang_code(self.source_language_id)

    @staticmethod
    def _to_language_id(lang_code):
        return f"l:{lang_code}"

    @staticmethod
    def _to_lang_code(language_id):
        return language_id.replace("l:", "")

    def move_resources(self, hq_lang_code, target_project, version=None, use_version_postfix=True):
        # not exposed to UI
        pass
