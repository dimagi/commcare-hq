from datetime import datetime, timedelta
from django.core.management import BaseCommand

from corehq.apps.saved_reports.models import ReportNotification


def get_domains(path):
    with open(path, 'r') as f:
        domains = f.readlines()

    return [domain.strip() for domain in domains]


def get_reports_by_domain(domain):
    key = [domain]
    reports = ReportNotification.view('reportconfig/user_notifications',
        reduce=False, include_docs=True, startkey=key, endkey=key + [{}])
    return reports


DAYS_IN_WEEK = 7


def adjust_report(report, forward=False):
    day = report.day + 1 if report.interval == 'weekly' else report.day  # account for 0-indexed days
    trigger_time = datetime.now().replace(hour=report.hour, minute=report.minute, day=day)

    if forward:
        trigger_time += timedelta(hours=1)
    else:
        trigger_time -= timedelta(hours=1)

    report.hour = trigger_time.hour
    if report.interval == 'weekly':
        report.day = (trigger_time.day - 1) % DAYS_IN_WEEK
    elif report.interval == 'monthly':
        report.day = trigger_time.day

    return report


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domains', nargs='+')
        parser.add_argument('-F', '--forward', action='store_true')

    def handle(self, domains, forward=False, *args, **kwargs):
        for domain in domains:
            print(f'processing domain: {domain}')
            reports = get_reports_by_domain(domain)

            for report in reports:
                previous_hour = report.hour
                report = adjust_report(report, forward)
                report.save()
                print(f'Updated hour on report {report._id} from {previous_hour} to {report.hour}')
