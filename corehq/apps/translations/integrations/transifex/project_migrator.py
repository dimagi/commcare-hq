from __future__ import absolute_import
from __future__ import unicode_literals

from collections import OrderedDict

from corehq.apps.translations.models import TransifexProject
from corehq.apps.translations.integrations.transifex.client import TransifexApiClient


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

    def _update_slugs(self):
        # ToDo: update slugs on transifex
        pass

    def _update_context(self, translations):
        # ToDo: update context on Menus and forms sheet
        pass

    def _upload_new_translations(self, translations):
        # ToDo: upload updated translations
        pass

    def _update_menus_and_forms_sheet(self):
        translations = OrderedDict()
        # ToDo: pull translations from transifex
        self._update_context(translations)
        return self._upload_new_translations(translations)

    def validate(self):
        ProjectMigrationValidator(self).valid()

    def migrate(self):
        self._update_slugs()
        self._update_menus_and_forms_sheet()


class ProjectMigrationValidator(object):
    def __init__(self, migrator):
        self.migrator = migrator

    def _ensure_same_source_lang(self):
        # ToDo: ensure same source lang for source app, target app and on transifex project
        pass

    def valid(self):
        self._ensure_same_source_lang()
