from __future__ import absolute_import, print_function, unicode_literals

from django.core.management import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_build_doc_by_version, wrap_app
from corehq.apps.app_manager.models import import_app


class Command(BaseCommand):
    help = "Make a copy of a specific version of an application on the same domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('app_id')
        parser.add_argument('version')
        parser.add_argument('new_name')

    def handle(self, domain, app_id, version, new_name, **options):
        old_app = get_build_doc_by_version(domain, app_id, version)
        if not old_app:
            raise Exception("No app found with id '{}' and version '{}', on '{}'"
                            .format(app_id, version, domain))
        old_app = wrap_app(old_app)
        old_app.convert_build_to_app()
        new_app = import_app(old_app.to_json(), domain, source_properties={'name': new_name})
