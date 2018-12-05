from __future__ import absolute_import
from __future__ import unicode_literals

from django.core.management import CommandError
from django.core.management.base import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_current_app, get_build_doc_by_version, \
    get_latest_released_app_doc, wrap_app
from corehq.apps.app_manager.views.utils import overwrite_app
from corehq.apps.userreports.util import get_static_report_mapping


class Command(BaseCommand):
    """
    Overwrites target application with other application
    """

    args = "<from_domain> <from_app_id> <to_domain> <to_app_id>"

    _report_map = None

    def add_arguments(self, parser):
        parser.add_argument('from_domain')
        parser.add_argument('from_app_id')
        parser.add_argument('to_domain')
        parser.add_argument('to_app_id')
        parser.add_argument(
            '--version',
            help="Specify version of 'from app' to use. If not specified the latest released version will be used."
        )

    def handle(self, from_domain, from_app_id, to_domain, to_app_id, *args, **options):
        self.from_domain = from_domain
        self.to_domain = to_domain
        app = get_current_app(self.to_domain, to_app_id)
        if options.get('version'):
            from_app_doc = get_build_doc_by_version(self.from_domain, from_app_id, options.get('version'))
        else:
            from_app_doc = get_latest_released_app_doc(self.from_domain, from_app_id)

        if not from_app_doc:
            raise CommandError("From app not found")

        from_app = wrap_app(from_app_doc)
        overwrite_app(app, from_app, self.report_map)

    @property
    def report_map(self):
        if not self._report_map:
            self._report_map = get_static_report_mapping(self.from_domain, self.to_domain)
        return self._report_map
