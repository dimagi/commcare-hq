import os
import tempfile

import polib
import requests
from transifex.api import TransifexApi
from transifex.api.exceptions import UploadException

from corehq.apps.translations.integrations.transifex.const import SOURCE_LANGUAGE_MAPPING


class TransifexApiClient(object):
    def __init__(self, token, organization, project, use_version_postfix=True):
        self.use_version_postfix = use_version_postfix
        self.api = TransifexApi(auth=token)
        self.organization = self.api.Organization.get(slug=organization)
        self.project = self.api.Project.get(slug=project, organization=self.organization)

    @property
    def _i18n_format(self):
        return self.api.I18nFormat(id="PO")

    @property
    def project_name(self):
        return self.project.name

    @property
    def source_language_id(self):
        return self.project.related["source_language"].id

    @property
    def source_lang_code(self):
        return self._to_lang_code(self.source_language_id)

    def _create_resource(self, resource_slug, resource_name):
        resource = self.api.Resource.create(
            name=resource_name,
            slug=resource_slug,
            project=self.project,
            i18n_format=self._i18n_format
        )
        return resource

    @staticmethod
    def _upload_content(cls, content, resource_id, language_id=None):
        # TransifexApi.upload() waits for async upload which we don't need, so create the upload manually
        data = {"resource": resource_id}
        if language_id is not None:
            data["language"] = language_id
        upload = cls.create_with_form(data=data, files={"content": content})

        # mirror TransifexApi error handling
        if hasattr(upload, "errors") and len(upload.errors) > 0:
            raise UploadException(upload.errors[0]["detail"], upload.errors)

    def _upload_resource_strings(self, content, resource_id):
        cls = self.api.ResourceStringsAsyncUpload
        self._upload_content(cls, content, resource_id)

    def _upload_resource_translations(self, content, resource_id, language_id):
        cls = self.api.ResourceTranslationsAsyncUpload
        self._upload_content(cls, content, resource_id, language_id=language_id)

    def _list_language_stats(self, resource_id=None, language_id=None):
        language_stats_list = self.api.ResourceLanguageStats.filter(project=self.project)
        if resource_id:
            language_stats_list.filter(resource=resource_id)
        if language_id:
            language_stats_list.filter(language=language_id)
        return language_stats_list

    def _get_resource(self, resource_slug):
        resource = self.api.Resource.get(slug=resource_slug, project=self.project)
        return resource

    def _list_resources(self):
        resources = self.api.Resource.filter(project=self.project)
        return resources

    @staticmethod
    def _download_content(cls, resource_id, language_id=None):
        if language_id is None:
            download = cls.download(resource=resource_id)
        else:
            download = cls.download(resource=resource_id, language=language_id)
        response = requests.get(download, stream=True)
        return response.content

    def _download_resource_strings(self, resource_id):
        cls = self.api.ResourceStringsAsyncDownload
        return self._download_content(cls, resource_id)

    def _download_resource_translations(self, resource_id, language_id):
        cls = self.api.ResourceTranslationsAsyncDownload
        return self._download_content(cls, resource_id, language_id=language_id)

    def delete_resource(self, resource_slug):
        resource = self._get_resource(resource_slug)
        resource.delete()

    def upload_resource(self, path_to_pofile, resource_slug, resource_name, update_resource):
        """
        Upload source language file

        :param path_to_pofile: path to pofile
        :param resource_slug: resource slug
        :param resource_name: resource name, mostly same as resource slug itself
        :param update_resource: update resource
        """
        if update_resource:
            resource = self._get_resource(resource_slug)
        else:
            # must create the new resource first
            if resource_name is None:
                __, filename = os.path.split(path_to_pofile)
                resource_name = filename
            resource = self._create_resource(name=resource_name, slug=resource_slug)
        content = open(path_to_pofile, 'r', encoding="utf-8").read()
        self._upload_resource_strings(content, resource.id)

    def upload_translation(self, path_to_pofile, resource_slug, hq_lang_code):
        """
        Upload translated files

        :param path_to_pofile: path to pofile
        :param resource_slug: resource slug
        :param hq_lang_code: lang code on hq
        """
        language_id = self._to_language_id(self.transifex_lang_code(hq_lang_code))
        resource = self._get_resource(resource_slug)
        content = open(path_to_pofile, 'r', encoding="utf-8").read()
        self._upload_resource_translations(content, resource.id, language_id)

    def get_resource_slugs(self, version):
        """
        :return: list of resource slugs corresponding to version
        """
        all_resources = self._list_resources()
        if version and self.use_version_postfix:
            # get all resources with version postfix
            return [r.slug for r in all_resources
                    if r.slug.endswith("v%s" % version)]
        elif version and not self.use_version_postfix:
            # get all resources that don't have version postfix
            return [r.slug for r in all_resources
                    if not r.slug.endswith("v%s" % version)]
        else:
            # get all resources
            return [r.slug for r in all_resources]

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
            f.write(content.decode(encoding="utf-8"))
        if lock_resource:
            resource.save(accept_translations=False)
        return polib.pofile(temp_file.name)

    def move_resource(self, old_resource_slug, new_resource_slug):
        old_resource = self._get_resource(slug=old_resource_slug)
        self._create_resource(new_resource_slug, old_resource.name)
        self.delete_resource(old_resource_slug)

    def get_project_langcodes(self):
        language_stats_list = self._list_language_stats()
        return [self._to_lang_code(stats.language.id) for stats in language_stats_list]

    def source_lang_is(self, hq_lang_code):
        """
        confirm is source lang on transifex is same as hq lang code
        """
        return self.transifex_lang_code(hq_lang_code) == self.source_lang_code

    def translation_completed(self, resource_slug, hq_lang_code=None):
        """
        check if a resource has been completely translated for
        all langs or a specific target lang
        """
        def completed(stats):
            return not bool(stats.untranslated_words)

        resource = self._get_resource(resource_slug)
        if hq_lang_code:
            language_id = self._to_language_id(self.transifex_lang_code(hq_lang_code))
            language_stats = self._list_language_stats(resource_id=resource.id, language_id=language_id)[0]
            return completed(language_stats)
        else:
            language_stats_list = self._list_language_stats(resource_id=resource.id)
            return all(completed(stats) for stats in language_stats_list)

    @staticmethod
    def transifex_lang_code(hq_lang_code):
        """
        Single place to convert lang codes from HQ to transifex lang code

        :param hq_lang_code: lang code on HQ
        """
        return SOURCE_LANGUAGE_MAPPING.get(hq_lang_code, hq_lang_code)

    @staticmethod
    def _to_language_id(lang_code):
        return f"l:{lang_code}"

    @staticmethod
    def _to_lang_code(language_id):
        return language_id.replace("l:", "")
