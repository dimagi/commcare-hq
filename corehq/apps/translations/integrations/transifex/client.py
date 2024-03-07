import json
import os
import tempfile

import polib
import requests
from transifex.api import TransifexApi
from transifex.api.exceptions import UploadException

from corehq.apps.translations.integrations.transifex.const import SOURCE_LANGUAGE_MAPPING
from corehq.apps.translations.integrations.transifex.exceptions import ResourceMissing


class TransifexApiClient(object):
    def __init__(self, token, organization, project, use_version_postfix=True):
        self.use_version_postfix = use_version_postfix
        self.api = TransifexApi(auth=token)
        self.organization = self.api.Organization.get(slug=organization)
        self.project = self.api.Project.get(slug=project, organization=self.organization)

    @property
    def _auth(self):
        return self.username, self.token

    @property
    def i18n_format(self):
        return self.api.I18nFormat(id="PO")

    @property
    def project_details(self):
        return self.project.to_dict()

    def list_resources_by_version(self, version):
        """
        :return: list of resources corresponding to version
        """
        all_resources = self.api.Resource.filter(project=self.project)
        if version and self.use_version_postfix:
            # get all resources with version postfix
            return [r for r in all_resources
                    if r.slug.endswith("v%s" % version)]
        elif version and not self.use_version_postfix:
            # get all resources that don't have version postfix
            return [r for r in all_resources
                    if not r.slug.endswith("v%s" % version)]
        else:
            # get all resources
            return all_resources

    @staticmethod
    def _create_with_form(cls, content, resource_id, language_id=None):
        # TransifexApi.upload() waits for async upload which we don't need, so create the upload manually
        data = {"resource": resource_id}
        if language_id is not None:
            data["language"] = language_id
        upload = cls.create_with_form(data=data, files={"content": content})

        # mirror TransifexApi error handling
        if hasattr(upload, "errors") and len(upload.errors) > 0:
            raise UploadException(upload.errors[0]["detail"], upload.errors)
        return upload

    def move_resource(self, old_resource_slug, new_resource_slug):
        # get the old resource
        old_resource = self.api.Resource.get(slug=old_resource_slug, project=self.project)

        # create the new resource
        new_resource = self.api.Resource(
            name=old_resource.name,
            slug=new_resource_slug,
            project=self.project,
            i18n_format=self.i18n_format
        )
        new_resource.save()

        # download source language strings from old resource
        download = self.api.ResourceStringsAsyncDownload.download(resource=old_resource)
        response = requests.get(download, stream=True)

        # upload source language strings for new resource
        cls = self.api.ResourceStringsAsyncUpload
        self._create_with_form(cls, response.content, new_resource.id)

        language_stats_list = self.api.ResourceLanguageStats.filter(resource=old_resource, project=self.project)
        for stats in language_stats_list:
            # download translations for each language
            language = stats.language
            if language == self.project.related["source_language"]:
                continue
            download = self.api.ResourceTranslationsAsyncDownload.download(
                resource=old_resource, language=language)
            response = requests.get(download, stream=True)

            # upload translations for new resource
            cls = self.api.ResourceTranslationsAsyncUpload
            self._create_with_form(cls, response.content, new_resource.id, language.id)

        return new_resource

    def delete_resource(self, resource_slug):
        resource = self.api.Resource.get(slug=resource_slug, project=self.project)
        return resource.delete()

    def upload_resource(self, path_to_pofile, resource_slug, resource_name, update_resource):
        """
        Upload source language file

        :param path_to_pofile: path to pofile
        :param resource_slug: resource slug
        :param resource_name: resource name, mostly same as resource slug itself
        :param update_resource: update resource
        """
        if update_resource:
            resource = self.api.Resource.get(slug=resource_slug, project=self.project)
        else:
            # must create the new resource first
            if resource_name is None:
                __, filename = os.path.split(path_to_pofile)
                resource_name = filename
            resource = self.api.Resource(
                name=resource_name,
                slug=resource_slug,
                project=self.project,
                i18n_format=self.i18n_format
            )
            resource.save()

        cls = self.api.ResourceStringsAsyncUpload
        content = open(path_to_pofile, 'r', encoding="utf-8").read()
        return self._create_with_form(cls, content, resource.id)

    def upload_translation(self, path_to_pofile, resource_slug, hq_lang_code):
        """
        Upload translated files

        :param path_to_pofile: path to pofile
        :param resource_slug: resource slug
        :param hq_lang_code: lang code on hq
        """
        language_id = self._lang_code_to_language_id(self.transifex_lang_code(hq_lang_code))
        resource = self.api.Resource.get(slug=resource_slug, project=self.project)

        cls = self.api.ResourceTranslationsAsyncUpload
        content = open(path_to_pofile, 'r', encoding="utf-8").read()
        return self._create_with_form(cls, content, resource.id, language_id)

    def translation_completed(self, resource_slug, hq_lang_code=None):
        """
        check if a resource has been completely translated for
        all langs or a specific target lang
        """
        def completed(stats):
            return not bool(stats.untranslated_words)

        resource = self.api.Resource.get(slug=resource_slug, project=self.project)
        if hq_lang_code:
            language_id = self._lang_code_to_language_id(self.transifex_lang_code(hq_lang_code))
            language = self.api.Language(id=language_id)
            language_stats = self.api.ResourceLanguageStats.get(
                language=language, resource=resource, project=self.project)
            return completed(language_stats)
        else:
            language_stats_list = self.api.ResourceLanguageStats.filter(
                resource=resource, project=self.project)
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
        language_id = self._lang_code_to_language_id(self.transifex_lang_code(hq_lang_code))
        language = self.api.Language(id=language_id)
        resource = self.api.Resource.get(slug=resource_slug, project=self.project)
        download = self.api.ResourceTranslationsAsyncDownload.download(resource=resource, language=language)
        response = requests.get(download, stream=True)
        temp_file = tempfile.NamedTemporaryFile()
        with open(temp_file.name, 'w', encoding='utf-8') as f:
            f.write(response.content.decode(encoding="utf-8"))
        if lock_resource:
            resource.save(accept_translations=False)
        return polib.pofile(temp_file.name)

    @staticmethod
    def _lang_code_to_language_id(lang_code):
        return f"l:{lang_code}"

    @staticmethod
    def _language_id_to_lang_code(language_id):
        return language_id.replace("l:", "")

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
        source_language = self.project.related["source_language"]
        return self._language_id_to_lang_code(source_language.id)

    def get_project_langs(self):
        """
        :return: list of lang codes used in project on transifex
        """
        language_stats_list = self.api.ResourceLanguageStats.filter(project=self.project)
        return [self._language_id_to_lang_code(stats.language.id) for stats in language_stats_list]

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
