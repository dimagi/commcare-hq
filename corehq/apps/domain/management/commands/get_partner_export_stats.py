from django.core.management.base import BaseCommand

from corehq.apps.app_manager.models import Application
from corehq.apps.export.models import FormExportInstance, CaseExportInstance
from corehq.util.quickcache import quickcache


class Command(BaseCommand):
    help = "Give stats on export downloads based on logs"
    slug = 'export_stats_for_partners'

    def add_arguments(self, parser):
        parser.add_argument(
            'export_type',
            help="form or case",
        )
        parser.add_argument(
            'export_ids',
            help="comma separated list of export_ids",
        )

    def handle(self, export_type, export_ids, **options):
        self.stdout.write('export id\texport type\tproject\texport name\tapp id\tapp name')
        export_ids = export_ids.split(',')
        for export_id in export_ids:
            self.print_export_info(export_id, export_type)

    @quickcache(['self.slug', 'app_id'])
    def get_app_name(self, app_id):
        app = Application.get(app_id)
        return app.name

    def print_export_info(self, export_id, export_type):
        export_class = {
            'form': FormExportInstance,
            'case': CaseExportInstance,
        }[export_type]
        export_instance = export_class.get(export_id)
        app_name = self.get_app_name(export_instance.app_id)
        self.stdout.write(f'{export_id}\t{export_type}\t{export_instance.domain}\t{export_instance.name}\t{export_instance.app_id}\t{app_name}')
