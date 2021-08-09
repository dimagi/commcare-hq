from django.core.management.base import BaseCommand

from corehq.apps.app_manager.models import Application
from corehq.apps.export.models import FormExportInstance, CaseExportInstance
from corehq.apps.userreports.models import report_config_id_is_static, \
    StaticReportConfiguration, ReportConfiguration
from corehq.util.couch import get_document_or_not_found
from corehq.util.quickcache import quickcache


class Command(BaseCommand):
    help = "Give stats on export downloads based on logs"
    slug = 'partner_export_stats'

    def add_arguments(self, parser):
        parser.add_argument(
            'log_file_path',
            help="path to log file",
        )
        parser.add_argument(
            'stat_type',
            help="exports,ucr,excel",
        )

    def handle(self, log_file_path, stat_type, **options):
        if stat_type == 'export':
            self.stdout.write(f'\nexport type\ttimestamp\tuser\tproject\texport id\texport name\tapp id\tapp name')
        if stat_type == 'ucr':
            self.stdout.write(f'\ttimestamp\tuser\tproject\treport id\treport name')
        if stat_type == 'excel':
            self.stdout.write(f'\ttimestamp\tuser\tproject\treport slug')

        with open(log_file_path, encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if stat_type == 'export':
                    self.show_export_data(line, 'form')
                    self.show_export_data(line, 'case')
                if stat_type == 'ucr':
                    self.show_ucr_data(line)
                if stat_type == 'excel':
                    self.show_export_to_excel_data(line)

    @quickcache(['self.slug', 'app_id'])
    def get_app_name(self, app_id):
        app = Application.get(app_id)
        return app.name

    @quickcache(['self.slug', 'export_id', 'export_type'])
    def get_export_info(self, export_id, export_type):
        export_class = {
            'form': FormExportInstance,
            'case': CaseExportInstance,
        }[export_type]
        export_instance = export_class.get(export_id)
        app_name = self.get_app_name(export_instance.app_id)
        return export_instance.name, export_instance.app_id, app_name

    def show_ucr_data(self, line):
        url_path = 'configurable_reports/export_status'
        if url_path in line:
            data = line.split(',')
            timestamp = data[0]
            user = data[1]
            domain = data[2]
            url = data[-1]
            ucr_id = url.split('/')[-2]
            report_config = self.get_ucr_config(ucr_id, domain)
            self.stdout.write(f'{timestamp}\t{user}\t{domain}\t{ucr_id}\t{report_config.title}')

    @quickcache(['self.slug', 'ucr_id', 'domain'])
    def get_ucr_config(self, ucr_id, domain):
        if report_config_id_is_static(ucr_id):
            return StaticReportConfiguration.by_id(ucr_id, domain=domain)
        else:
            return get_document_or_not_found(ReportConfiguration, domain, ucr_id)

    def show_export_data(self, line, export_type):
        export_url_path = f'data/export/custom/new/{export_type}/download'
        if export_url_path in line:
            data = line.split(',')
            timestamp = data[0]
            user = data[1]
            domain = data[2]
            url = data[-1]
            export_id = url.split('/')[-2]
            export_info = self.get_export_info(export_id, export_type)
            self.stdout.write(f'{export_type}\t{timestamp}\t{user}\t{domain}\t{export_id}\t{export_info[0]}\t{export_info[1]}\t{export_info[2]}')

    def show_export_to_excel_data(self, line):
        url_path = 'reports/export'
        if url_path in line and not 'configurable_reports' in line:
            data = line.split(',')
            timestamp = data[0]
            user = data[1]
            domain = data[2]
            url = data[-1]
            report_slug = url.split('/')[-2]
            self.stdout.write(f'\t{timestamp}\t{user}\t{domain}\t{report_slug}')
