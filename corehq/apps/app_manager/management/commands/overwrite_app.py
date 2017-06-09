from django.core.management.base import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_current_app_doc, get_app, wrap_app
from corehq.apps.app_manager.models import Application, ReportModule
from corehq.apps.userreports.util import copy_static_reports


class Command(BaseCommand):
    """
    Overwrites target application with other application
    """

    args = "<from_domain> ><from_app_id> <to_domain> <to_app_id>"

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
        excluded_fields = set(Application._meta_fields).union(
            ['date_created', 'build_profiles', 'copy_history', 'copy_of', 'name', 'comment', 'doc_type']
        )
        master_json = latest_master_build.to_json()
        for key, value in master_json.iteritems():
            if key not in excluded_fields:
                app[key] = value
        app['version'] = master_json['version']
        wrapped_app = wrap_app(app)
        for module in wrapped_app.modules:
            if isinstance(module, ReportModule):
                for config in module.report_configs:
                    config.report_id = self.report_map[config.report_id]
        wrapped_app.copy_attachments(latest_master_build)
        wrapped_app.save(increment_version=False)

    @property
    def report_map(self):
        if not self._report_map:
            self._report_map = {}
            copy_static_reports(self.from_domain, self.to_domain, self._report_map)
        return self._report_map
