import itertools
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand

from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.apps.es import CaseES, FormES


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domains', nargs="*",
            help='Domains to check, will include enterprise-controlled child domains.'
        )
        parser.add_argument('--num-days', type=int, default=30, help='Number of days (UTC) to inspect')

    def handle(self, domains, **options):
        filename = "form_case_counts_{}".format(datetime.utcnow().strftime("%Y-%m-%d_%H.%M.%S"))
        for row in self.get_rows(domains, options['num_days']):
            if row['forms_submitted']:
                print(row)

    def get_rows(self, domains, num_days):
        end = date.today()
        start = end - timedelta(days=num_days)
        for domain in _expand_domains(domains):
            submissions_counts = _get_submissions_counts(domain, start, end)

            day = start
            while day <= end:
                yield {
                    'domain': domain,
                    'date': day.isoformat(),
                    'forms_submitted': submissions_counts.get(day, 0),
                }
                day += timedelta(days=1)


def _expand_domains(domains):
    return sorted(set(itertools.chain(
        domains,
        *(EnterprisePermissions.get_domains(domain) for domain in domains)
    )))


def _get_datetime_range(num_days):
    now = datetime.utcnow()
    end = datetime(now.year, now.month, now.day)  # 00:00:00 this morning UTC
    start = end - timedelta(days=num_days)
    return start, end

def _get_submissions_counts(domain, start, end):
    res = (FormES()
           .domain(domain)
           .submitted(gte=start, lte=end)
           .submitted_histogram()
           .run().aggregations.date_histogram)
    return {
        date.fromisoformat(bucket['key_as_string']): bucket['doc_count']
        for bucket in res.normalized_buckets
    }
