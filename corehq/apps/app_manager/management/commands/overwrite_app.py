from django.core.management import CommandError
from django.core.management.base import BaseCommand

from corehq.apps.app_manager.dbaccessors import (
    get_build_doc_by_version,
    get_current_app,
    get_latest_released_app_doc,
    wrap_app,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.views.utils import overwrite_app
from corehq.apps.userreports.util import get_static_report_mapping


class Command(BaseCommand):
    """
    Overwrites target application with other application
    """

    args = "<from_domain> <from_app_id> <to_domain>"

    _report_map = None

    def add_arguments(self, parser):
        parser.add_argument('from_domain')
        parser.add_argument('from_app_id')
        parser.add_argument('to_domain')
        parser.add_argument(
            '--to-app-id',
            help="Overwrite this app. A new app will be created if not specified."
        )
        parser.add_argument(
            '--version',
            help="Specify version of 'from app' to use. If not specified the latest released version will be used."
        )

    def handle(self, from_domain, from_app_id, to_domain, *args, **options):
        self.from_domain = from_domain
        self.to_domain = to_domain
        to_app_id = options.get('to-app-id')
        version = options.get('version')
        if to_app_id:
            app = get_current_app(self.to_domain, to_app_id)
            print('Overwriting application: {}'.format(app.name))
        else:
            print('Creating new application')
            app = Application()

        if version:
            from_app_doc = get_build_doc_by_version(self.from_domain, from_app_id, version)
        else:
            from_app_doc = get_latest_released_app_doc(self.from_domain, from_app_id)

        if not from_app_doc:
            raise CommandError("From app not found")

        from_app = wrap_app(from_app_doc)
        print('Overwring app with "{}" (version {})'.format(from_app.name, from_app.version))
        overwrite_app(app, from_app, self.report_map)

    @property
    def report_map(self):
        if not self._report_map:
            self._report_map = get_static_report_mapping(self.from_domain, self.to_domain)
        return self._report_map
