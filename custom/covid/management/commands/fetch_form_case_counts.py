import csv
import itertools
from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand

from corehq.apps.enterprise.models import EnterprisePermissions
from corehq.apps.es import CaseES, FormES
from corehq.apps.es.aggregations import (
    DateHistogram,
    NestedAggregation,
    TermsAggregation,
)
from corehq.util.argparse_types import date_type


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--domains', nargs="*",
            help='Domains to check, will include enterprise-controlled child domains.'
        )
        parser.add_argument('--start', type=date_type, help='Start date (inclusive)')
        parser.add_argument('--end', type=date_type, help='End date (inclusive)')

    def handle(self, domains, start, end, **options):
        filename = "form_case_counts_{}.csv".format(datetime.utcnow().strftime("%Y-%m-%d_%H.%M.%S"))
        case_types = sorted(_get_case_types(domains))
        with open(filename, 'w', encoding='utf-8') as csv_file:
            field_names = ['domain', 'date', 'form_submissions'] + case_types + ['cases_opened']
            csv_writer = csv.DictWriter(csv_file, field_names)
            csv_writer.writeheader()
            for row in self.get_rows(domains, case_types, start, end):
                csv_writer.writerow(row)
        print(f"Result saved to {filename}")

    def get_rows(self, domains, case_types, start, end):
        for domain in _expand_domains(domains):
            submissions_counts = _get_submissions_counts(domain, start, end)
            case_update_counts = _get_case_update_counts(domain, start, end)
            case_opened_counts = _get_case_opened_counts(domain, start, end)

            day = start
            while day <= end:
                yield {
                    'domain': domain,
                    'date': day.isoformat(),
                    'form_submissions': submissions_counts.get(day, 0),
                    **{
                        case_type: case_update_counts.get((case_type, day), 0)
                        for case_type in case_types
                    },
                    'cases_opened': case_opened_counts.get(day, 0)
                }
                day += timedelta(days=1)


def _expand_domains(domains):
    return sorted(set(itertools.chain(
        domains,
        *(EnterprisePermissions.get_domains(domain) for domain in domains)
    )))


def _get_case_types(domains):
    return (CaseES()
            .domain(domains)
            .terms_aggregation("type.exact", "case_types")
            .run().aggregations.case_types.keys)


def _get_submissions_counts(domain, start, end):
    res = (FormES()
           .remove_default_filters()
           .domain(domain)
           .submitted(gte=start, lte=end)
           .aggregation(
               DateHistogram('date_histogram', 'inserted_at', DateHistogram.Interval.DAY))
           .run().aggregations.date_histogram)
    return {
        date.fromisoformat(bucket['key']): bucket['doc_count']
        for bucket in res.normalized_buckets
    }


def _get_case_update_counts(domain, start, end):
    res = (CaseES()
           .domain(domain)
           .active_in_range(gte=start, lte=end)
           .aggregation(
               TermsAggregation('case_types', 'type.exact')
               .aggregation(
                   NestedAggregation('actions', 'actions').aggregation(
                       DateHistogram('case_count', 'actions.server_date', DateHistogram.Interval.DAY)
                   )
               )
           )
           .run())

    ret = {}
    for case_type in res.aggregations.case_types.buckets_list:
        for case_count in case_type.actions.case_count.normalized_buckets:
            day = date.fromisoformat(case_count['key'])
            ret[(case_type.key, day)] = case_count['doc_count']
    return ret


def _get_case_opened_counts(domain, start, end):
    res = (CaseES()
           .domain(domain)
           .active_in_range(gte=start, lte=end)
           .aggregation(
               DateHistogram('date_histogram', 'opened_on', DateHistogram.Interval.DAY))
           .run().aggregations.date_histogram)

    return {
        date.fromisoformat(bucket['key']): bucket['doc_count']
        for bucket in res.normalized_buckets
    }
