from __future__ import absolute_import
from __future__ import unicode_literals
from collections import Counter

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from corehq.apps.data_pipeline_audit.dbacessors import get_primary_db_case_counts, get_primary_db_form_counts, \
    get_es_counts_by_doc_type
from corehq.apps.data_pipeline_audit.utils import map_counter_doc_types
from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_class
from corehq.apps.dump_reload.couch.dump import DOC_PROVIDERS
from corehq.apps.dump_reload.couch.id_providers import DocTypeIDProvider
from corehq.apps.dump_reload.sql.dump import get_model_iterator_builders_to_dump
from corehq.apps.dump_reload.util import get_model_label
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.apps.users.dbaccessors.all_commcare_users import get_web_user_count, get_mobile_user_count
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.util.couch import get_document_class_by_doc_type
from corehq.util.markup import CSVRowFormatter, TableRowFormatter, SimpleTableWriter


class Command(BaseCommand):
    help = "Print database stats for a domain. Use in conjunction with 'compare_docs_with_es'."

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--csv', action='store_true', default=False, dest='csv',
                            help='Write output in CSV format.')

    def handle(self, domain, **options):
        csv = options.get('csv')

        couch_counts = map_counter_doc_types(_get_couchdb_counts(domain))
        sql_counts = map_counter_doc_types(_get_sql_counts(domain))
        es_counts = map_counter_doc_types(get_es_counts_by_doc_type(domain))
        all_doc_types = set(couch_counts) | set(sql_counts) | set(es_counts)

        output_rows = []
        for doc_type in sorted(all_doc_types, key=lambda d: d.lower()):
            couch = couch_counts.get(doc_type, '')
            sql = sql_counts.get(doc_type, '')
            es = es_counts.get(doc_type, '')
            output_rows.append((doc_type, couch, sql, es))

        if csv:
            row_formatter = CSVRowFormatter()
        else:
            row_formatter = TableRowFormatter(
                [50, 20, 20, 20],
                _get_row_color
            )

        SimpleTableWriter(self.stdout, row_formatter).write_table(
            ['Doc Type', 'Couch', 'SQL', 'ES'], output_rows
        )


def _get_row_color(row):
    doc_type, couch_count, sql_count, es_count = row
    couch_dff = couch_count and couch_count != es_count
    sql_diff = sql_count and sql_count != es_count
    if es_count and (couch_dff or sql_diff):
        return 'red'


def _get_couchdb_counts(domain):
    couch_db_counts = Counter()
    for provider in DOC_PROVIDERS:
        if isinstance(provider, DocTypeIDProvider):
            for doc_type in provider.doc_types:
                if doc_type == 'CommCareUser':
                    continue  # want to split deleted
                doc_class = get_document_class_by_doc_type(doc_type)
                count = get_doc_count_in_domain_by_class(domain, doc_class)
                couch_db_counts.update({doc_type: count})

    for row in CommCareMultimedia.get_db().view('hqmedia/by_domain', key=domain, include_docs=False):
        couch_db_counts.update(['CommCareMultimedia'])

    mobile_user_count = get_mobile_user_count(domain)
    couch_db_counts.update({
        'WebUser': get_web_user_count(domain),
        'CommCareUser': mobile_user_count,
        'CommCareUser-Deleted': get_doc_count_in_domain_by_class(domain, CommCareUser) - mobile_user_count
    })

    # this is very slow, excluding for now
    # for _, doc_ids in SyncLogIDProvider().get_doc_ids(domain):
    #     couch_db_counts['SyncLog'] += len(doc_ids)
    #
    return couch_db_counts


def _get_sql_counts(domain):
    counter = Counter()
    for model_class, builder in get_model_iterator_builders_to_dump(domain, []):
        if model_class in (User, XFormInstanceSQL, CommCareCaseSQL):
            continue  # User is very slow, others we want to break out
        for queryset in builder.querysets():
            counter[get_model_label(model_class)] += queryset.count()

    counter += get_primary_db_form_counts(domain)
    counter += get_primary_db_case_counts(domain)
    return counter
