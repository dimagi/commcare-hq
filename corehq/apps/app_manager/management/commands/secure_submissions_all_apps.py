from distutils.version import LooseVersion
from django.core.management import BaseCommand
from corehq.apps.app_manager.const import APP_V2
from corehq.apps.app_manager.util import all_apps_by_domain
from corehq.apps.builds import get_default_build_spec


def turn_on_secure_submissions_for_all_apps(domain):
    for app in all_apps_by_domain(domain):
        print app
        save = False
        if app.application_version == '1.0':
            continue
        if LooseVersion(app.build_spec.version) < '2.8':
            app.build_spec = get_default_build_spec(APP_V2)
            save = True
        if not app.secure_submissions:
            app.secure_submissions = True
            save = True
        if save:
            app.save()


class Command(BaseCommand):
    def handle(self, *args, **options):
        domains = list(args)
        for domain in domains:
            turn_on_secure_submissions_for_all_apps(domain)
