from django.core.management.base import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_current_app_doc, get_app
from corehq.apps.app_manager.views.utils import overwrite_app
from corehq.apps.userreports.util import get_static_report_mapping


class Command(BaseCommand):
    """
    Overwrites target application with other application
    """

    args = "<from_domain> <from_app_id> <to_domain> <to_app_id>"

    def add_arguments(self, parser):
        parser.add_argument('from_domain')
        parser.add_argument('from_app_id')
        parser.add_argument('to_domain')
        parser.add_argument('to_app_id')

    def handle(self, from_domain, from_app_id, to_domain, to_app_id, *args, **options):
        self.from_domain = from_domain
        self.to_domain = to_domain
        app = get_current_app_doc(self.to_domain, to_app_id)
        latest_master_build = get_app(None, from_app_id, latest=True)
        overwrite_app(app, latest_master_build, include_ucrs=True, report_map=self.report_map)

    @property
    def report_map(self):
        if not self._report_map:
            self._report_map = get_static_report_mapping(self.from_domain, self.to_domain, {})
        return self._report_map
