from corehq.toggles import SYNC_SEARCH_CASE_CLAIM

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.management.commands.helpers import get_all_app_ids


class Command(BaseCommand):

    def handle(self, **options):
        domains = sorted(SYNC_SEARCH_CASE_CLAIM.get_enabled_domains())
        for domain in domains:
            print(f"Looking at domain: {domain}")
            app_ids = get_all_app_ids(domain)  # , include_builds=True)
            for app_id in app_ids:
                app = Application.get(app_id)
                print(f"Checking Application Modules: {app_id}")
                for module in app.modules:
                    if hasattr(module, 'search_config'):
                        print(f"Looking at Module: {module.name}")
                        title_label = module.search_config.title_label
                        new_title_label = {}
                        for lang, string in title_label.items():
                            if string is None:
                                print(f"Fixing translation: {{{lang}: {string}}}")
                                new_title_label[lang] = ""
                            else:
                                new_title_label[lang] = string
                        module.search_config.title_label = new_title_label
                app.save()
