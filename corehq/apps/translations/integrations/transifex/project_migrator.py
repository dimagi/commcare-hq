import copy
import datetime
import tempfile
from collections import OrderedDict

from django.utils.functional import cached_property
from django.utils.translation import gettext as _

import polib
from memoized import memoized

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.translations.integrations.transifex.client import (
    TransifexApiClient,
)
from corehq.apps.translations.integrations.transifex.const import (
    SOURCE_LANGUAGE_MAPPING,
    TRANSIFEX_SLUG_PREFIX_MAPPING,
)
from corehq.apps.translations.integrations.transifex.exceptions import (
    InvalidProjectMigration,
    ResourceMissing,
)
from corehq.apps.translations.models import TransifexProject


class ProjectMigrator(object):
    def __init__(self, domain, project_slug, source_app_id, target_app_id, resource_ids_mapping):
        """
        Migrate a transifex project from one app to another by
        1. updating slugs of resources to use new module/form ids
        2. updating context of translations in "Menus_and_forms" sheet to use new module/form ids
        :param resource_ids_mapping: tuple of type, old_id, new_id
        """
        self.domain = domain
        self.project_slug = project_slug
        self.project = TransifexProject.objects.get(slug=project_slug)
        self.client = TransifexApiClient(self.project.organization.get_api_token, self.project.organization,
                                         project_slug)
        self.source_app_id = source_app_id
        self.target_app_id = target_app_id
        self.resource_ids_mapping = resource_ids_mapping
        self.id_mapping = {old_id: new_id for _, old_id, new_id in self.resource_ids_mapping}

    def validate(self):
        ProjectMigrationValidator(self).validate()

    def migrate(self):
        slug_update_responses = self._update_slugs()
        menus_and_forms_sheet_update_responses = self._update_menus_and_forms_sheet()
        return slug_update_responses, menus_and_forms_sheet_update_responses

    def _update_slugs(self):
        responses = {}
        for resource_type, old_id, new_id in self.resource_ids_mapping:
            slug_prefix = self._get_slug_prefix(resource_type)
            if not slug_prefix:
                continue
            resource_slug = "%s_%s" % (slug_prefix, old_id)
            new_resource_slug = "%s_%s" % (slug_prefix, new_id)
            responses[old_id] = self.client.update_resource_slug(resource_slug, new_resource_slug)
        return responses

    @memoized
    def _get_slug_prefix(self, resource_type):
        return TRANSIFEX_SLUG_PREFIX_MAPPING.get(resource_type)

    def _update_menus_and_forms_sheet(self):
        langs = copy.copy(self.source_app_langs)
        translations = OrderedDict()
        for lang in langs:
            try:
                translations[lang] = self.client.get_translation("Menus_and_forms", lang, lock_resource=False)
            except ResourceMissing:
                # Probably a lang in app not present on Transifex, so skip
                pass
        self._update_context(translations)
        return self._upload_new_translations(translations)

    @cached_property
    def source_app_langs(self):
        return self._source_app.langs

    @cached_property
    def _source_app(self):
        return get_app(self.domain, self.source_app_id)

    def _update_context(self, translations):
        """
        update msgctxt for all POEntry objects replacing ids
        :param translations: dict of lang code mapped to it list of POEntries
        """
        for po_entries in translations.values():
            for po_entry in po_entries:
                # make sure the format is as expected, if not skip
                context_entries = po_entry.msgctxt.split(":")
                if len(context_entries) == 3:
                    resource_id = context_entries[-1]
                    # replace if we have been asked to replace it
                    if resource_id in self.id_mapping:
                        po_entry.msgctxt = po_entry.msgctxt.replace(resource_id, self.id_mapping[resource_id])

    def _upload_new_translations(self, translations):
        responses = {}
        # the project source lang, which is the app default language should be the first to update.
        # HQ keeps the default lang on top and hence it should be the first one here
        assert list(translations.keys())[0] == self.target_app_default_lang
        for lang_code in translations:
            responses[lang_code] = self._upload_translation(translations[lang_code], lang_code)
        return responses

    def _upload_translation(self, translations, lang_code):
        po = polib.POFile()
        po.check_for_duplicates = False
        po.metadata = self.get_metadata()
        po.extend(translations)
        with tempfile.NamedTemporaryFile() as temp_file:
            po.save(temp_file.name)
            temp_file.seek(0)
            if lang_code == self.target_app_default_lang:
                self.client.upload_resource(temp_file.name, "Menus_and_forms", "Menus_and_forms", True)
            else:
                self.client.upload_translation(temp_file.name, "Menus_and_forms", lang_code)

    def get_metadata(self):
        now = str(datetime.datetime.now())
        return {
            'App-Id': self.target_app_id,
            'PO-Creation-Date': now,
            'MIME-Version': '1.0',
            'Content-Type': 'text/plain; charset=utf-8',
            'Language': self.target_app_default_lang
        }

    @cached_property
    def target_app_default_lang(self):
        return self._target_app.default_language

    @cached_property
    def _target_app(self):
        return get_app(self.domain, self.target_app_id)

    @cached_property
    def get_project_source_lang(self):
        return self.client.source_lang_code

    @cached_property
    def source_app_default_lang(self):
        return self._source_app.default_language


class ProjectMigrationValidator(object):
    def __init__(self, migrator):
        self.migrator = migrator
        self.source_app_default_lang = migrator.source_app_default_lang
        self.target_app_default_lang = migrator.target_app_default_lang

    def validate(self):
        self._ensure_same_source_lang()

    def _ensure_same_source_lang(self):
        """
        ensure same source lang for source app, target app and on transifex project
        """
        if not self.source_app_default_lang or (self.source_app_default_lang != self.target_app_default_lang):
            raise InvalidProjectMigration(
                _("Target app default language and the source app default language don't match"))

        project_source_lang = self.migrator.get_project_source_lang
        source_app_lang_code = SOURCE_LANGUAGE_MAPPING.get(self.source_app_default_lang,
                                                           self.source_app_default_lang)
        if source_app_lang_code != project_source_lang:
            raise InvalidProjectMigration(
                _("Transifex project source lang and the source app default language don't match"))

        target_app_lang_code = SOURCE_LANGUAGE_MAPPING.get(self.target_app_default_lang,
                                                           self.target_app_default_lang)

        if target_app_lang_code != project_source_lang:
            raise InvalidProjectMigration(
                _("Transifex project source lang and the target app default language don't match"))
