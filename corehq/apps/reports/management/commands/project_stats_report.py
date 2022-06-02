from collections import defaultdict
from datetime import date, datetime

from django.core.management import BaseCommand
from django.db import ProgrammingError, connections, models, router
from django.db.models import Count, F, Func
from django.db.models.aggregates import Avg, StdDev

from dateutil.relativedelta import relativedelta

from corehq.apps.data_analytics.models import MALTRow
from corehq.apps.es import CaseES, FormES, UserES
from corehq.apps.es.aggregations import (
    DateHistogram,
    NestedAggregation,
    TermsAggregation,
)
from corehq.apps.reports.standard.project_health import (
    get_performance_threshold,
)
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    StaticDataSourceConfiguration,
)
from corehq.apps.userreports.util import get_table_name
from corehq.blobs.models import BlobMeta
from corehq.form_processor.models import (
    LedgerTransaction,
    LedgerValue,
)
from corehq.form_processor.models.cases import CommCareCase
from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.connections import connection_manager
from corehq.sql_db.util import (
    estimate_row_count,
    get_db_aliases_for_partitioned_query,
    split_list_by_db_partition,
)
from corehq.util.markup import (
    CSVRowFormatter,
    SimpleTableWriter,
    TableRowFormatter,
)
from casexml.apps.phone.models import SyncLogSQL


RESOURCE_MODEL_STATS = [
    'total_users',
    'monthly_forms_per_user',
    'monthly_cases_per_user',
    'monthly_user_form_stats_expanded',
    'monthly_user_case_stats_expanded',
    'monthly_user_cases_updated',
    'case_index_ratio',
    'attachments',
    'forms_total',
    'cases_total',
    'case_transactions_per_form',
    'case_transactions_total',
    'synclogs_per_user',
    'static_datasources',
    'dynamic_datasources',
    'datasources_info',
    'devicelogs_per_user',
]


class ResourceModel(object):

    def __init__(self, dictionary):
        self._dictionary = dictionary

    def __setitem__(self, key, item):
        if key not in self._dictionary:
            raise KeyError("The key {} is not defined.".format(key))
        self._dictionary[key] = item

    def __getitem__(self, key):
        return self._dictionary[key]


resource_model_stats_dict = {key: '' for key in RESOURCE_MODEL_STATS}
resource_model = ResourceModel(resource_model_stats_dict)


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
            UserES(for_export=True)
            .domain(domain).values_list("_id", flat=True)
        )

        self.collect_doc_counts()
        self.collect_forms_per_user_per_month()
        self.collect_cases_created_per_user_per_month()
        self.collect_cases_updated_per_user_per_month()
        self.collect_case_transactions()
        self.collect_case_indices()
        self.collect_synclogs()
        self.collect_devicelogs()
        self.collect_ledgers_per_case()
        self.collect_attachment_sizes()
        self.collect_ucr_data()

        self.output_stats()

    def collect_doc_counts(self):
        resource_model['forms_total'] = FormES().domain(self.domain).count()
        resource_model['cases_total'] = CaseES().domain(self.domain).count()

    def collect_forms_per_user_per_month(self):
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

        total_users = 0
        total_average_forms = 0
        months = 0

        for stat in user_stat_from_malt:
            total_average_forms += stat['avg_forms']
            total_users += stat['num_users']
            months += 1

        resource_model['total_users'] = total_users

        if months > 0:
            resource_model['monthly_forms_per_user'] = total_average_forms/months

        monthly_user_stats = user_stat_from_malt\
            .filter(user_type__in=['CommCareUser'])\
            .filter(user_id__in=self.active_not_deleted_users)\
            .filter(num_of_forms__gte=performance_threshold)

        resource_model['monthly_user_form_stats_expanded'] = monthly_user_stats

    def collect_cases_created_per_user_per_month(self, case_type=None):
        query = (
            CaseES(for_export=True).domain(self.domain)
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
        total_average_cases_per_user = 0
        n = 0
        for month, case_count_list in sorted(list(stats.items()), key=lambda r: r[0]):
            average_cases_per_user = sum(case_count_list) // len(case_count_list)
            total_average_cases_per_user += average_cases_per_user
            n += 1
            final_stats.append((month, average_cases_per_user))

        if n > 0:
            resource_model['monthly_cases_per_user'] = total_average_cases_per_user/n

        resource_model['monthly_user_case_stats_expanded'] = final_stats

    def _print_table(self, headers, rows):
        if self.csv:
            row_formatter = CSVRowFormatter()
        else:
            row_formatter = TableRowFormatter(
                [20] * len(headers),
            )

        SimpleTableWriter(self.stdout, row_formatter).write_table(headers, rows)
        self.stdout.write('')

    def _print_section_title(self, title_string):
        self.stdout.write('')
        self.stdout.write(f'{title_string.upper()}')
        self.stdout.write('=' * len(title_string))

    def _print_value(self, name, *values):
        separator = ',' if self.csv else ': '
        values = [str(val) for val in values]
        self.stdout.write('\n%s%s%s\n' % (name, separator, separator.join(values)))

    def collect_cases_updated_per_user_per_month(self):
        results = (
            CaseES(for_export=True).domain(self.domain)
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

        resource_model['monthly_user_cases_updated'] = final_stats

    def collect_ledgers_per_case(self):
        case_ids = set()
        ledger_count = 0

        for db_name in get_db_aliases_for_partitioned_query():
            results = (
                LedgerValue.objects.using(db_name).filter(domain=self.domain)
                .values('case_id')
                .annotate(ledger_count=Count('pk'))
            )

            for result in results:
                case_ids.add(result['case_id'])
                ledger_count += result['ledger_count']

        if not case_ids:
            self.stdout.write("Domain has no ledgers")
            return

        avg_ledgers_per_case = ledger_count / len(case_ids)
        case_types_result = CaseES(for_export=True)\
            .domain(self.domain).case_ids(case_ids)\
            .aggregation(TermsAggregation('types', 'type.exact'))\
            .size(0).run()

        case_types = case_types_result.aggregations.types.keys

        self.stdout.write('\nCase Types with Ledgers')
        for type_ in case_types:
            self._print_value('case_type', type_, CaseES().domain(self.domain).case_type(type_).count())
            db_name = get_db_aliases_for_partitioned_query()[0]  # just query one shard DB
            results = (
                CommCareCase.objects.using(db_name).filter(domain=self.domain, closed=True, type=type_)
                .annotate(lifespan=F('closed_on') - F('opened_on'))
                .annotate(avg_lifespan=Avg('lifespan'))
                .values('avg_lifespan', flat=True)
            )
            self._print_value('Average lifespan for "%s" cases' % type_, results[0]['avg_lifespan'])

            self._cases_created_per_user_per_month(type_)

        self._print_value('Average ledgers per case', avg_ledgers_per_case)

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

        final_stats = []
        for month, transaction_count_list in sorted(list(stats.items()), key=lambda r: r[0]):
            final_stats.append((month.isoformat(), sum(transaction_count_list) // len(transaction_count_list)))

        self.stdout.write('Ledger updates per case')
        self._print_table(['Month', 'Ledgers updated per case'], final_stats)

    def collect_attachment_sizes(self):
        result = []

        for db_name in get_db_aliases_for_partitioned_query():
            with BlobMeta.get_cursor_for_partition_db(db_name, readonly=True) as cursor:
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
                result = result + [i for i in fetchall_as_namedtuple(cursor)]

        resource_model['attachments'] = result

    def collect_ucr_data(self):
        static_datasources = StaticDataSourceConfiguration.by_domain(self.domain)
        dynamic_datasources = DataSourceConfiguration.by_domain(self.domain)

        resource_model['static_datasources'] = len(static_datasources)
        resource_model['dynamic_datasources'] = len(dynamic_datasources)

        def _get_count(config):
            table_name = get_table_name(config.domain, config.table_id)
            db_name = connection_manager.get_django_db_alias(config.engine_id)
            query = ('SELECT * FROM "%s"' % table_name, [])
            try:
                return estimate_row_count(query, db_name)
            except ProgrammingError:
                return "Table not found"

        def _get_table_size(config):
            table_name = get_table_name(config.domain, config.table_id)
            db_name = connection_manager.get_django_db_alias(config.engine_id)
            db_cursor = connections[db_name].cursor()
            with db_cursor as cursor:
                try:
                    cursor.execute("SELECT pg_total_relation_size('\"%s\"')" % table_name, [])
                    bytes = cursor.fetchone()[0]
                    return bytes
                except ProgrammingError:
                    return "Table not found"

        rows = sorted([
            (
                datasource.display_name, _get_count(datasource),
                datasource.referenced_doc_type, _get_table_size(datasource)
            )
            for datasource in static_datasources + dynamic_datasources
        ], key=lambda r: r[-1] if r[-1] != 'Table not found' else 0)

        resource_model['datasources_info'] = rows

    def collect_case_transactions(self):
        total_form_case_updates = 0
        total_forms = 0
        total_transactions = 0

        for db_name in get_db_aliases_for_partitioned_query():
            db_cursor = connections[db_name].cursor()

            with db_cursor as cursor:
                cursor.execute("""
                    SELECT COUNT(*) as num_forms, sum(d.count) as num_updates
                    FROM (
                        SELECT COUNT(*) as count
                        FROM form_processor_casetransaction t 
                        JOIN form_processor_commcarecasesql c on t.case_id = c.case_id
                        WHERE c.domain = %s
                        GROUP BY form_id
                    ) AS d
                """, [self.domain])
                result = cursor.fetchall()
                forms, form_case_updates = (0, 0)
                if result:
                    forms, form_case_updates = result[0]

                total_forms += forms
                total_form_case_updates += form_case_updates

                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM form_processor_casetransaction t 
                    JOIN form_processor_commcarecasesql c on t.case_id = c.case_id
                    WHERE c.domain = %s
                """, [self.domain])
                (transactions,) = cursor.fetchone()
                total_transactions += transactions

        resource_model['case_transactions_per_form'] = total_form_case_updates / total_forms
        resource_model['case_transactions_total'] = total_transactions

    def collect_case_indices(self):
        total_case_indices = 0
        for db_name in get_db_aliases_for_partitioned_query():
            db_cursor = connections[db_name].cursor()

            with db_cursor as cursor:
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM form_processor_commcarecaseindexsql
                    WHERE domain = %s;
                """, [self.domain])
                (case_indices,) = cursor.fetchone()
                total_case_indices += case_indices

        total_cases = resource_model['cases_total']
        if total_cases > 0:
            resource_model['case_index_ratio'] = total_case_indices/total_cases
        else:
            resource_model['case_index_ratio'] = 0

    def collect_synclogs(self):
        db_name = router.db_for_read(SyncLogSQL)
        db_cursor = connections[db_name].cursor()

        with db_cursor as cursor:
            cursor.execute("""
                SELECT COUNT(*), sum(d.count)
                FROM (
                    SELECT COUNT(*) AS count
                    FROM phone_synclogsql
                    WHERE domain = %s
                    GROUP BY user_id
                ) AS d
            """, [self.domain])
            result = cursor.fetchall()

            total_users, total_user_synclogs = (0, 0)
            if result:
                total_users, total_user_synclogs = result[0]

            if total_users > 0:
                resource_model['synclogs_per_user'] = total_user_synclogs / total_users
            else:
                resource_model['synclogs_per_user'] = 0

    def collect_devicelogs(self):
        from phonelog.models import DeviceReportEntry
        device_log_data = DeviceReportEntry.objects.filter(domain=self.domain)\
            .aggregate(
                num_authors=Count('user_id', distinct=True),
                num_device_logs=Count('id'),
        )

        devicelogs_per_user = \
            device_log_data['num_device_logs'] // device_log_data['num_authors'] if device_log_data['num_authors'] > 0 else 0

        resource_model['devicelogs_per_user'] = devicelogs_per_user

    def output_stats(self):
        self._print_section_title('Docs count')
        self._output_docs_count()

        self._print_section_title('User stats')
        self._output_monthly_user_form_stats()
        self._output_monthly_user_case_stats()

        self._print_section_title('Case Indices')
        self._output_case_ratio_index()

        self._print_section_title('Case Transactions')
        self._output_case_transactions()

        self._print_section_title('Sync logs')
        self._output_synclogs()

        self._print_section_title('Device logs')
        self._output_devicelogs()

        self._print_section_title('Attachments')
        self._output_attachment_sizes()

        self._print_section_title('UCR')
        self._output_ucr()

    def _output_docs_count(self):
        total_forms = resource_model['forms_total']
        self.stdout.write(f'Total forms: {total_forms}')

        total_cases = resource_model['cases_total']
        self.stdout.write(f'Total cases: {total_cases}')

    def _output_monthly_user_form_stats(self):
        def _format_rows(query_):
            return [
                (row['month'].isoformat(), row['num_users'], row['avg_forms'], row['std_dev'])
                for row in query_
            ]

        user_stats = resource_model['monthly_user_form_stats_expanded']
        headers = ['Month', 'Active Users', 'Average forms per user', 'Std Dev']

        self._print_table(
            headers,
            _format_rows(
                user_stats
            )
        )

        monthly_forms_per_user = resource_model['monthly_forms_per_user']
        self.stdout.write(f'Average forms per user per month: {monthly_forms_per_user}')

        self.stdout.write('')
        self.stdout.write('System user stats')
        self._print_table(
            headers,
            _format_rows(user_stats.filter(username='system'))
        )

    def _output_monthly_user_case_stats(self, case_type=None):
        case_stats = resource_model['monthly_user_case_stats_expanded']

        suffix = ''
        if case_type:
            suffix = '(case type: %s)' % case_type
        self.stdout.write('Cases created per user (estimate)')
        self._print_table(['Month', 'Cases created per user %s' % suffix], case_stats)

        case_updates = resource_model['monthly_user_cases_updated']
        self.stdout.write('Cases updated per user (estimate)')
        self._print_table(['Month', 'Cases updated per user'], case_updates)

        monthly_cases_per_user = resource_model['monthly_cases_per_user']
        self.stdout.write(f'Average cases per user per month: {monthly_cases_per_user}')

    def _output_case_ratio_index(self):
        case_index_ratio = resource_model['case_index_ratio']
        self.stdout.write(f'Ratio of cases to case indices: 1 : {case_index_ratio}')

    def _output_attachment_sizes(self):
        attachments = resource_model['attachments']

        self.stdout.write('Form attachment sizes (bytes)')
        self._print_table(
            ['Content Type', 'Count', 'Bucket range', 'Bucket (1-10)'],
            [
                (row.content_type, row.freq, '[%s-%s]' % (row.bucket_min, row.bucket_max), row.bucket)
                for row in attachments
            ]
        )

    def _output_ucr(self):
        self.stdout.write(f"Static UCR data sources: {resource_model['static_datasources']}")
        self.stdout.write(f"Dynamic UCR data sources: {resource_model['dynamic_datasources']}")

        rows = resource_model['datasources_info']

        self.stdout.write('')
        self.stdout.write('UCR datasource sizes')
        self._print_table(
            ['Datasource name', 'Row count (approximate)', 'Doc type', 'Size (bytes)'],
            rows
        )

    def _output_case_transactions(self):
        case_transactions = resource_model['case_transactions_per_form']
        self.stdout.write(f'Average cases updated per form: {case_transactions}')

        case_transactions_total = resource_model['case_transactions_total']
        self.stdout.write(f'Total case transactions: {case_transactions_total}')

    def _output_synclogs(self):
        synclogs_per_user = resource_model['synclogs_per_user']
        self.stdout.write(f'Synclogs per user: {synclogs_per_user}')

    def _output_devicelogs(self):
        synclogs_per_user = resource_model['devicelogs_per_user']
        self.stdout.write(f'Device logs per user: {synclogs_per_user}')
