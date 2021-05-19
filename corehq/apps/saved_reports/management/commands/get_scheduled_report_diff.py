import datetime
import re

from django.core.management import BaseCommand

from corehq.apps.reports.daterange import get_daterange_start_end_dates
from corehq.apps.saved_reports.models import ReportNotification, ReportConfig


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('scheduled_report_id')
        parser.add_argument('past_date')

    def handle(self, domain, scheduled_report_id, past_date, *args, **options):
        past_date = datetime.datetime.strptime(past_date, '%Y-%m-%d').date()
        handle(domain, scheduled_report_id, past_date)


def handle(domain, scheduled_report_id, past_date):
    scheduled_report = ReportNotification.get(scheduled_report_id)
    assert scheduled_report.doc_type == 'ReportNotification'
    assert scheduled_report.domain == domain
    ReportNotification.save = ReportNotification.delete = ReportNotification.bulk_save = ReportNotification.bulk_delete = NotImplemented
    ReportConfig.save = ReportConfig.delete = ReportConfig.bulk_save = ReportConfig.bulk_delete = NotImplemented

    for config in scheduled_report.configs:
        if config.is_configurable_report:
            print(filter_to_relevant_lines(get_report_content_for_past_date(
                config, past_date).text))
    return scheduled_report


def get_report_content_for_dates(config, start_date, end_date):
    try:
        _get_date_range = ReportConfig.get_date_range

        def get_date_range(self):
            dates = {
                'startdate': start_date.isoformat(),
                'enddate': end_date.isoformat(),
            }
            filter_slug = self.datespan_slug
            if filter_slug:
                return {
                    '%s-start' % filter_slug: start_date.isoformat(),
                    '%s-end' % filter_slug: end_date.isoformat(),
                    filter_slug: '%(startdate)s to %(enddate)s' % dates,
                }
            else:
                return {}

        ReportConfig.get_date_range = get_date_range
        return config.get_report_content('en')
    finally:
        ReportConfig.get_date_range = _get_date_range
        config._query_string_cache = {}


def get_report_content_for_past_date(config, past_date):
    start_date, end_date = get_daterange_start_end_dates(
        config.date_range,
        start_date=config.start_date,
        end_date=config.end_date,
        days=config.days,
        today=past_date,
    )
    print(f'date={past_date} start_date={start_date} end_date={end_date}')
    return get_report_content_for_dates(config, start_date, end_date)


def filter_to_relevant_lines(report_text):
    text = '\n'.join(
        line for line in report_text.split('\n')
        if 'tr>' in line
        or 'th>' in line
        or 'td>' in line
    )
    text = re.sub(r'\s*<tr>\s*<th>\s*', '', text, flags=re.RegexFlag.MULTILINE)
    text = re.sub(r'</t[dh]>\s*<t[dh]>', '\t', text, flags=re.RegexFlag.MULTILINE)
    text = re.sub(r'\s*</t[dh]>\s*</tr>\s*<tr>\s*<t[dh]>\s*', '\n', text, flags=re.RegexFlag.MULTILINE)
    text = re.sub(r'\s*</td>\s*</tr>\s*', '\t', text, flags=re.RegexFlag.MULTILINE)
    return text
