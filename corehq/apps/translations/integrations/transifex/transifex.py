from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from corehq.apps.app_manager.dbaccessors import get_version_build_id
from corehq.apps.translations.const import MODULES_AND_FORMS_SHEET_NAME
from corehq.apps.translations.generators import (
    AppTranslationsGenerator,
    PoFileGenerator,
)
from corehq.apps.translations.integrations.transifex.client import (
    TransifexApiClient,
)
from corehq.apps.translations.integrations.transifex.parser import (
    TranslationsParser,
)
from corehq.apps.translations.models import TransifexProject


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
        :param exclude_if_default: ignore translation if its same as the source lang when pushing target langs
        :param use_version_postfix: use version number at the end of resource slugs
        :param update_resource: update resource file
        """
        if version:
            version = int(version)
        self.version = version
        self.domain = domain
        self.app_id = app_id
        self.key_lang = "en"  # the lang in which the string keys are, should be english
        self.lang_prefix = lang_prefix
        self.project_slug = project_slug
        self._resource_slugs = resource_slugs
        self.is_source_file = is_source_file
        self.exclude_if_default = exclude_if_default
        self.source_lang = source_lang
        self.lock_translations = lock_translations
        self.use_version_postfix = use_version_postfix
        self.update_resource = update_resource

    @cached_property
    def build_id(self):
        if self.version:
            return get_version_build_id(self.domain, self.app_id, self.version)
        else:
            return self.app_id

    def send_translation_files(self):
        """
        submit translation files to transifex
        """
        app_trans_generator = AppTranslationsGenerator(
            self.domain, self.build_id, self.version,
            self.key_lang, self.source_lang, self.lang_prefix,
            self.exclude_if_default, self.use_version_postfix)
        with PoFileGenerator(app_trans_generator.translations,
                             app_trans_generator.metadata) as po_file_generator:
            generated_files = po_file_generator.generate_translation_files()
            return self._send_files_to_transifex(generated_files, app_trans_generator)

    @cached_property
    def client(self):
        transifex_project = TransifexProject.objects.get(slug=self.project_slug)
        transifex_organization = transifex_project.organization
        return TransifexApiClient(
            transifex_organization.get_api_token,
            transifex_organization.slug,
            self.project_slug,
            self.use_version_postfix,
        )

    @cached_property
    def transifex_project_source_lang(self):
        return self.client.transifex_lang_code(self.client.source_lang_code)

    def _resource_name_in_project_lang(self, resource_slug, app_trans_generator):
        """
        return the name of the resource i.e module/form in source lang on Transifex

        :param resource_slug: like module_moduleUniqueID
        """
        if MODULES_AND_FORMS_SHEET_NAME in resource_slug:
            return MODULES_AND_FORMS_SHEET_NAME
        module_or_form_unique_id = resource_slug.split('_')[1]
        resource_name_in_all_langs = app_trans_generator.slug_to_name[module_or_form_unique_id]
        return resource_name_in_all_langs.get(self.transifex_project_source_lang,
                                              resource_name_in_all_langs.get('en', resource_slug))

    def _send_files_to_transifex(self, generated_files, app_trans_generator):
        file_uploads = {}
        for resource_slug, path_to_file in generated_files:
            resource_name = self._resource_name_in_project_lang(resource_slug, app_trans_generator)
            if self.is_source_file:
                response = self.client.upload_resource(
                    path_to_file,
                    resource_slug,
                    resource_name,
                    self.update_resource
                )
            else:
                response = self.client.upload_translation(
                    path_to_file,
                    resource_slug,
                    self.source_lang
                )
            if response.status_code in [200, 201]:
                file_uploads[resource_name] = _("Successfully Uploaded")
            else:
                file_uploads[resource_name] = "{}: {}".format(response.status_code, response.content)
        return file_uploads

    @cached_property
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

    def resources_pending_translations(self, all_langs=False):
        """
        :param all_langs: check for all langs for translation, if False just the source lang
        :return: first resource slug that is found with pending translations
        """
        check_for_lang = None if all_langs else self.source_lang
        for resource_slug in self.resource_slugs:
            if not self.client.is_translation_completed(resource_slug, check_for_lang):
                return resource_slug

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
