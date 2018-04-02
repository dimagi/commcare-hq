from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from corehq.apps.app_manager.const import APP_V1
from corehq.apps.app_manager.util import all_apps_by_domain
from corehq.apps.builds import get_default_build_spec


def turn_on_secure_submissions_for_all_apps(domain):
    for app in all_apps_by_domain(domain):
        save = False
        if app.application_version == APP_V1:
            continue
        if app.build_version < '2.8':
            app.build_spec = get_default_build_spec()
            save = True
        if not app.secure_submissions:
            app.secure_submissions = True
            save = True
        if save:
            app.save()


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domains',
            metavar='domain',
            nargs='*',
        )

    def handle(self, domains, **options):
        for domain in domains:
            turn_on_secure_submissions_for_all_apps(domain)
