from django.core.management.base import BaseCommand

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
            self.stdout.write(f'\nexport type\ttimestamp\tuser\tproject\texport id')
        if stat_type == 'ucr':
            self.stdout.write(f'\ntimestamp\tuser\tproject\treport id\treport name')
        if stat_type == 'excel':
            self.stdout.write(f'\ntimestamp\tuser\tproject\treport slug')

        with open(log_file_path, encoding='utf-8') as f:
            lines = f.readlines()
            form_export_ids = []
            case_export_ids = []
            for line in lines:
                if stat_type == 'export':
                    self.show_export_data(line, 'form', form_export_ids)
                    self.show_export_data(line, 'case', case_export_ids)
                if stat_type == 'ucr':
                    self.show_ucr_data(line)
                if stat_type == 'excel':
                    self.show_export_to_excel_data(line)

        if stat_type == 'export':
            self.stdout.write('\n\nFORM IDS')
            unique_form_exports = ','.join(set(form_export_ids))
            self.stdout.write(f'"{unique_form_exports}"')
            self.stdout.write('\n\nCASE IDS')
            unique_case_exports = ','.join(set(case_export_ids))
            self.stdout.write(f'"{unique_case_exports}"')

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

    def show_export_data(self, line, export_type, export_ids):
        export_url_path = f'data/export/custom/new/{export_type}/download'
        if export_url_path in line:
            data = line.split(',')
            timestamp = data[0]
            user = data[1]
            domain = data[2]
            url = data[-1]
            export_id = url.split('/')[-2]
            export_ids.append(export_id)
            self.stdout.write(f'{export_type}\t{timestamp}\t{user}\t{domain}\t{export_id}')

    def show_export_to_excel_data(self, line):
        url_path = 'reports/export'
        if url_path in line and not 'configurable_reports' in line:
            data = line.split(',')
            timestamp = data[0]
            user = data[1]
            domain = data[2]
            url = data[-1]
            report_slug = url.split('/')[-2]
            self.stdout.write(f'{timestamp}\t{user}\t{domain}\t{report_slug}')
