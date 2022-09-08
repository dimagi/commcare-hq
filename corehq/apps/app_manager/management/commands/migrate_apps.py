from corehq.toggles import SYNC_SEARCH_CASE_CLAIM
from django.core.management.base import BaseCommand
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.management.commands.helpers import get_all_app_ids
from couchdbkit.exceptions import ResourceNotFound
from lxml.etree import XMLSyntaxError


class Command(BaseCommand):
    """
    Migrates case.search.title translation value
    to case.search_config.title model attribute
    for all 2.53 apps and later
    """

    def handle(self, **options):
        domains = sorted(SYNC_SEARCH_CASE_CLAIM.get_enabled_domains())
        for domain in domains:
            app_ids = get_all_app_ids(domain)
            total_apps = len(app_ids)
            for i, app_id in enumerate(app_ids):
                self.progress_bar(domain, i, total_apps)
                current_app = Application.get(app_id)
                try:
                    self.migrate(current_app)
                    errors = current_app.validate_app()
                    if errors:
                        continue
                except XMLSyntaxError:
                    pass
                current_app.save()

    def _needs_to_be_migrated(self, version):
        major, minor, patch = [int(x) for x in version.split('.')]
        return major >= 2 and minor >= 53

    def migrate(self, app):
        if not self._needs_to_be_migrated(app['build_spec'].version):
            return False
        try:
            translations = app.translations
            for module in app.modules:
                self._migrate_module(translations, module)
        except (ResourceNotFound, AttributeError):
            pass
        return True

    def _migrate_module(self, translations, module):
        search_config = getattr(module, 'search_config')
        default_label_dict = getattr(search_config, 'title_label')
        label_dict = {lang: label.get('case.search.title')
            for lang, label in translations.items() if label and not default_label_dict[lang]}
        label_dict.update(default_label_dict)
        setattr(search_config, 'title_label', label_dict)

    def progress_bar(self, domain, current, total):
        print("   Migrating apps in %s %d/%d [%-20s] %d%%" %
            (domain, current + 1, total,
            '=' * int((20 * (current / total))),
            (current / total) * 100), end="\r")
        print()  # prevents the progress bar from deleting from the console, needed for debugging
