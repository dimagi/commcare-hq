import re
from django.core.management import BaseCommand
from couchdbkit import ResourceNotFound

from corehq.apps.saved_reports.models import ReportNotification

from .daylight_savings import adjust_report


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('file_path')

    def handle(self, file_path, *args, **kwargs):
        parser = LogParser()
        with open(file_path, 'r') as f:
            parser.parse_file(f)


DOMAIN_REGEX = re.compile(r'processing domain: ([\w-]+)')
LINE_REGEX = re.compile(r'Updated hour on report (\w+) from (\d+) to (\d+)')

INDEX_DOMAIN = 1

INDEX_REPORT_ID = 1
INDEX_ORIGINAL_HOUR = 2
INDEX_CHANGED_HOUR = 3


class LogParser:
    def reset_stats(self):
        self.reports_fixed = {}
        self.reports_ignored = {}
        self.reports_missing = {}

        self.current_domain = ''
        self.domains = []

        self.hours = {}

    def parse_file(self, file):
        self.reset_stats()

        for line in file.readlines():
            line_handled = self.handle_domain_line(line)
            if not line_handled:
                line_handled = self.handle_report_line(line)
            if not line_handled:
                print(f'Ignoring line: {line}')

        self.print_summary()

    def handle_domain_line(self, line):
        domain_match = DOMAIN_REGEX.search(line)
        if not domain_match:
            return False

        self.current_domain = domain_match.group(INDEX_DOMAIN)
        self.domains.append(self.current_domain)

        print(f'Processing domain {self.current_domain}')
        return True

    def handle_report_line(self, line):
        report_match = LINE_REGEX.search(line)
        if not report_match:
            return False

        report_id = report_match.group(INDEX_REPORT_ID)
        changed_hour = int(report_match.group(INDEX_CHANGED_HOUR))

        try:
            report = ReportNotification.get(report_id)
        except ResourceNotFound:
            missing_reports = self.reports_missing.get(self.current_domain, [])
            missing_reports.append(report_id)
            self.reports_missing[self.current_domain] = missing_reports
            return True

        if report.hour != changed_hour:
            ignored_domain_reports = self.reports_ignored.get(self.current_domain, [])
            ignored_domain_reports.append(report_id)
            self.reports_ignored[self.current_domain] = ignored_domain_reports
            print(f'Ignoring modified report: {report_id}')
        else:
            # the report was modified incorrectly, so let's fix it
            previous_hour = report.hour
            adjust_report(report, forward=True)
            adjust_report(report, forward=True)
            report.save()
            changed_reports = self.reports_fixed.get(self.current_domain, [])
            changed_reports.append(report_id)
            self.reports_fixed[self.current_domain] = changed_reports
            print(f'Updated report: {report_id} from {previous_hour} to {report.hour}')

        return True

    def print_summary(self):
        total_updated = 0
        total_ignored = 0
        total_missing = 0

        for domain in self.domains:
            updated_report_count = len(self.reports_fixed.get(domain, []))
            ignored_report_count = len(self.reports_ignored.get(domain, []))
            missing_report_count = len(self.reports_missing.get(domain, []))

            total_updated += updated_report_count
            total_ignored += ignored_report_count
            total_missing += missing_report_count

            print(f'Domain: {domain}')
            print(f'  updated reports: {updated_report_count}')
            print(f'  ignored reports: {ignored_report_count}')
            if missing_report_count:
                print(f'  missing reports: {missing_report_count}')

        total = total_updated + total_ignored + total_missing
        print('---------------------------')
        print(f'Total Updated: {total_updated} ({total_updated/total*100}%)')
        print(f'Total Ignored: {total_ignored} ({total_ignored/total*100}%)')
        print(f'Total Missing: {total_missing} ({total_missing/total*100}%)')
