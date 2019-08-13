from __future__ import absolute_import

from __future__ import unicode_literals
import re
from collections import defaultdict
from datetime import datetime, date

from dateutil.relativedelta import relativedelta
from django.core.management import BaseCommand
from django.db import models, connections
from django.db.models import Func, F, Count
from django.db.models.aggregates import Avg, StdDev

from casexml.apps.stock.models import StockTransaction
from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.es import UserES, CaseES, FormES
from corehq.apps.es.aggregations import TermsAggregation, DateHistogram, NestedAggregation
from corehq.apps.reports.standard.project_health import get_performance_threshold
from corehq.apps.userreports.models import DataSourceConfiguration, StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_table_name
from corehq.elastic import ES_EXPORT_INSTANCE
from corehq.form_processor.models import LedgerValue, LedgerTransaction, CommCareCaseSQL, CommCareCaseIndexSQL
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.connections import connection_manager
from corehq.sql_db.util import split_list_by_db_partition, get_db_aliases_for_partitioned_query
from corehq.util.markup import CSVRowFormatter, TableRowFormatter, SimpleTableWriter


class Month(Func):
    function = 'EXTRACT'
    template = '%(function)s(MONTH from %(expressions)s)'
    output_field = models.IntegerField()


class Year(Func):
    function = 'EXTRACT'
    template = '%(function)s(YEAR from %(expressions)s)'
    output_field = models.IntegerField()


class Command(BaseCommand):
    help = """Print out project stats for use by the cluster utilization model\n
    https://drive.google.com/drive/folders/0Bz-nswrLHmApbExCOVJ6TkgzeDQ
    """

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('-m', '--months', default=3, type=int, help="Months to average data over")
        parser.add_argument(
            '--include-current', action='store_true', default=False, help="Include the current month"
        )
        parser.add_argument('--csv', action='store_true', default=False, help="Output as CSV")

    def handle(self, domain, months, csv, **options):
        self.domain = domain
        self.csv = csv

        self.date_start = (datetime.utcnow() - relativedelta(months=months)).date().replace(day=1)
        self.date_end = None if options['include_current'] else datetime.utcnow().date().replace(day=1)

        self.active_not_deleted_users = (
            UserES(es_instance_alias=ES_EXPORT_INSTANCE)
            .domain(domain).values_list("_id", flat=True)
        )

        self._forms_per_user_per_month()
        self._cases_created_per_user_per_month()
        self._cases_updated_per_user_per_month()
        self._case_to_case_index_ratio()
        self._ledgers_per_case()
        self._attachment_sizes()
        self._ucr()

    def _doc_counts(self):
        self._print_value('Total cases', CaseES().domain(self.domain).count())
        self._print_value('Open cases', CaseES().domain(self.domain).is_closed(False).count())
        self._print_value('Total forms', FormES().domain(self.domain).count())

    def _forms_per_user_per_month(self):
        performance_threshold = get_performance_threshold(self.domain)
        base_queryset = MALTRow.objects.filter(
            domain_name=self.domain,
            month__gte=self.date_start,
        )

        if self.date_end:
            base_queryset.filter(month__lt=self.date_end)

        user_stat_from_malt = (
            base_queryset.values('month')
            .annotate(
                num_users=Count('user_id'),
                avg_forms=Avg('num_of_forms'),
                std_dev=StdDev('num_of_forms')
            )
        )

        def _format_rows(query_):
            return [
                (row['month'].isoformat(), row['num_users'], row['avg_forms'], row['std_dev'])
                for row in query_
            ]

        headers = ['Month', 'Active Users', 'Average forms per user', 'Std Dev']
        self.stdout.write('All user stats')
        self._print_table(
            headers,
            _format_rows(
                user_stat_from_malt
                .filter(user_type__in=['CommCareUser'])
                .filter(user_id__in=self.active_not_deleted_users)
                .filter(num_of_forms__gte=performance_threshold)
            )
        )

        self.stdout.write('System user stats')
        self._print_table(
            headers,
            _format_rows(user_stat_from_malt.filter(username='system'))
        )

    def _cases_created_per_user_per_month(self, case_type=None):
        query = (
            CaseES(es_instance_alias=ES_EXPORT_INSTANCE).domain(self.domain)
            .opened_range(gte=self.date_start, lt=self.date_end)
            .aggregation(
                TermsAggregation('cases_per_user', 'owner_id', size=100)
                .aggregation(DateHistogram('cases_by_date', 'opened_on', interval='month')))
        )
        if case_type:
            query = query.case_type(case_type)

        results = query.size(0).run()

        stats = defaultdict(list)
        cases_per_user = results.aggregations.cases_per_user
        for bucket in cases_per_user.buckets_list:
            counts_by_date = {b['key_as_string']: b['doc_count'] for b in bucket.cases_by_date.normalized_buckets}
            for key, count in counts_by_date.items():
                stats[key].append(count)

        final_stats = []
        for month, case_count_list in sorted(list(stats.items()), key=lambda r: r[0]):
            final_stats.append((month, sum(case_count_list) // len(case_count_list)))

        suffix = ''
        if case_type:
            suffix = '(case type: %s)' % case_type
        self._print_table(['Month', 'Cases created per user %s' % suffix], final_stats)

    def _print_table(self, headers, rows):
        if self.csv:
            row_formatter = CSVRowFormatter()
        else:
            row_formatter = TableRowFormatter(
                [20] * len(headers),
            )

        SimpleTableWriter(self.stdout, row_formatter).write_table(headers, rows)
        self.stdout.write('')

    def _print_value(self, name, *values):
        separator = ',' if self.csv else ': '
        values = [str(val) for val in values]
        self.stdout.write('\n%s%s%s\n' % (name, separator, separator.join(values)))

    def _cases_updated_per_user_per_month(self):
        results = (
            CaseES(es_instance_alias=ES_EXPORT_INSTANCE).domain(self.domain)
            .active_in_range(gte=self.date_start, lt=self.date_end)
            .aggregation(TermsAggregation('cases_per_user', 'owner_id', size=100).aggregation(
                NestedAggregation('actions', 'actions').aggregation(
                    DateHistogram('cases_by_date', 'server_date', interval='month')
                )
            )).size(0).run())

        stats = defaultdict(list)
        cases_per_user = results.aggregations.cases_per_user
        for bucket in cases_per_user.buckets_list:
            counts_by_date = {
                b['key_as_string']: b['doc_count']
                for b in bucket.actions.cases_by_date.normalized_buckets
            }
            for key, count in counts_by_date.items():
                stats[key].append(count)

        final_stats = []
        for month, case_count_list in sorted(list(stats.items()), key=lambda r: r[0]):
            final_stats.append((month, sum(case_count_list) // len(case_count_list)))

        self._print_table(['Month', 'Cases updated per user'], final_stats)

    def _ledgers_per_case(self):
        if should_use_sql_backend(self.domain):
            db_name = get_db_aliases_for_partitioned_query()[0]  # just query one shard DB
            results = (
                LedgerValue.objects.using(db_name).filter(domain=self.domain)
                .values('case_id')
                .annotate(ledger_count=Count('pk'))
            )[:100]
        else:
            raise NotImplementedError

        case_ids = set()
        ledger_count = 0
        for result in results:
            case_ids.add(result['case_id'])
            ledger_count += result['ledger_count']

        if not case_ids:
            self.stdout.write("Domain has no ledgers")
            return

        avg_ledgers_per_case = ledger_count // len(case_ids)
        case_types_result = CaseES(es_instance_alias=ES_EXPORT_INSTANCE)\
            .domain(self.domain).case_ids(case_ids)\
            .aggregation(TermsAggregation('types', 'type'))\
            .size(0).run()

        case_types = case_types_result.aggregations.types.keys

        self.stdout.write('\nCase Types with Ledgers')
        for type_ in case_types:
            self._print_value('case_type', type_, CaseES().domain(self.domain).case_type(type_).count())
            if should_use_sql_backend(self.domain):
                db_name = get_db_aliases_for_partitioned_query()[0]  # just query one shard DB
                results = (
                    CommCareCaseSQL.objects.using(db_name).filter(domain=self.domain, closed=True, type=type_)
                    .annotate(lifespan=F('closed_on') - F('opened_on'))
                    .annotate(avg_lifespan=Avg('lifespan'))
                    .values('avg_lifespan', flat=True)
                )
                self._print_value('Average lifespan for "%s" cases' % type_, results[0]['avg_lifespan'])

            self._cases_created_per_user_per_month(type_)

        self._print_value('Average ledgers per case', avg_ledgers_per_case)

        if should_use_sql_backend(self.domain):
            stats = defaultdict(list)
            for db_name, case_ids_p in split_list_by_db_partition(case_ids):
                transactions_per_case_per_month = (
                    LedgerTransaction.objects.using(db_name).filter(case_id__in=case_ids)
                    .annotate(m=Month('server_date'), y=Year('server_date')).values('case_id', 'y', 'm')
                    .annotate(count=Count('id'))
                )
                for row in transactions_per_case_per_month:
                    month = date(row['y'], row['m'], 1)
                    stats[month].append(row['count'])
        else:
            transactions_per_case_per_month = (
                StockTransaction.objects.filter(case_id__in=case_ids)
                .annotate(m=Month('report__date'), y=Year('report__date')).values('case_id', 'y', 'm')
                .annotate(count=Count('id'))
            )

            stats = defaultdict(list)
            for row in transactions_per_case_per_month:
                month = date(row['y'], row['m'], 1)
                stats[month].append(row['count'])

        final_stats = []
        for month, transaction_count_list in sorted(list(stats.items()), key=lambda r: r[0]):
            final_stats.append((month.isoformat(), sum(transaction_count_list) // len(transaction_count_list)))

        self._print_table(['Month', 'Ledgers updated per case'], final_stats)

    def _case_to_case_index_ratio(self):
        if not should_use_sql_backend(self.domain):
            self.stdout.write('\nUnable to get case to index ratio of Couch domain\n')
            return

        db_name = get_db_aliases_for_partitioned_query()[0]  # just query one shard DB
        case_count = _get_count_from_explain(
            db_name, CommCareCaseSQL.objects.using(db_name).filter(domain=self.domain)
        )
        case_index_count = _get_count_from_explain(
            db_name, CommCareCaseIndexSQL.objects.using(db_name).filter(domain=self.domain)
        )
        self._print_value('Ratio of cases to case indices', case_count // float(case_index_count))

    def _attachment_sizes(self):
        if not should_use_sql_backend(self.domain):
            self.stdout.write('\nAttachment stats only available for SQL domains\n')
            return

        db_name = get_db_aliases_for_partitioned_query()[0]  # just query one shard DB
        cursor = connections[db_name].cursor()
        with cursor:
            cursor.execute("""
                SELECT
                    meta.content_type,
                    width_bucket(content_length, 0, 2900000, 10) AS bucket,
                    min(content_length) as bucket_min, max(content_length) AS bucket_max,
                    count(content_length) AS freq
                FROM blobs_blobmeta meta INNER JOIN form_processor_xforminstancesql
                  ON meta.parent_id = form_processor_xforminstancesql.form_id
                WHERE content_length IS NOT NULL AND form_processor_xforminstancesql.domain = %s
                GROUP BY content_type, bucket
                ORDER BY content_type, bucket
            """, [self.domain])

            self._print_table(
                ['Content Type', 'Count', 'Bucket range', 'Bucket (1-10)'],
                [
                    (row.content_type, row.freq, '[%s-%s]' % (row.bucket_min, row.bucket_max), row.bucket)
                    for row in fetchall_as_namedtuple(cursor)
                ]
            )

    def _ucr(self):
        static_datasources = StaticDataSourceConfiguration.by_domain(self.domain)
        dynamic_datasources = DataSourceConfiguration.by_domain(self.domain)
        self._print_value('Static UCR data sources', len(static_datasources))
        self._print_value('Dynamic UCR data sources', len(dynamic_datasources))

        def _get_count(config):
            table_name = get_table_name(config.domain, config.table_id)
            db_name = connection_manager.get_django_db_alias(config.engine_id)
            return _get_count_from_explain_raw(
                db_name,
                'SELECT * FROM "%s"' % table_name,
                []
            )

        def _get_table_size(config):
            table_name = get_table_name(config.domain, config.table_id)
            db_name = connection_manager.get_django_db_alias(config.engine_id)
            db_cursor = connections[db_name].cursor()
            with db_cursor as cursor:
                cursor.execute("SELECT pg_total_relation_size('\"%s\"')" % table_name, [])
                bytes = cursor.fetchone()[0]
                return bytes

        rows = sorted([
            (
                datasource.display_name, _get_count(datasource),
                datasource.referenced_doc_type, _get_table_size(datasource)
            )
            for datasource in static_datasources + dynamic_datasources
        ], key=lambda r: r[-1])

        self._print_table(
            ['Datasource name', 'Row count (approximate)', 'Doc type', 'Size', 'Size (bytes)'],
            rows
        )


def _get_count_from_explain(from_db, query):
    sql, params = query.query.sql_with_params()
    return _get_count_from_explain_raw(from_db, sql, params)


def _get_count_from_explain_raw(from_db, raw_query, params):
    explain_query = 'EXPLAIN {}'.format(raw_query)
    db_cursor = connections[from_db].cursor()
    with db_cursor as cursor:
        cursor.execute(explain_query, params)
        for row in cursor.fetchall():
            search = re.search(r' rows=(\d+)', row[0])
            if search:
                return int(search.group(1))
    return 0
