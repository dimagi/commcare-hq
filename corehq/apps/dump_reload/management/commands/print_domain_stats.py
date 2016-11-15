from collections import Counter

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from corehq.apps import es
from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_class
from corehq.apps.dump_reload.couch.dump import DOC_PROVIDERS
from corehq.apps.dump_reload.couch.id_providers import DocTypeIDProvider
from corehq.apps.dump_reload.sql.dump import get_querysets_to_dump, allow_form_processing_queries
from corehq.apps.dump_reload.util import get_model_label
from corehq.apps.hqmedia.models import CommCareMultimedia
from corehq.apps.users.dbaccessors.all_commcare_users import get_web_user_count, get_mobile_user_count
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import doc_type_to_state
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.sql_db.config import get_sql_db_aliases_in_use
from corehq.util.couch import get_document_class_by_doc_type
from corehq.util.markup import shell_red

DOC_TYPE_MAPPING = {
    'xforminstance': 'XFormInstance',
    'submissionerrorlog': 'SubmissionErrorLog',
    'xformduplicate': 'XFormDuplicate',
    'xformerror': 'XFormError',
    'xformarchived': 'XFormArchived',
}


class Command(BaseCommand):
    help = "Print database stats for a domain. Use in conjunction with 'compare_docs_with_es'."
    args = '<domain>'

    def add_arguments(self, parser):
        parser.add_argument('--csv', action='store_true', default=False, dest='csv',
                            help='Write output in CSV format.')

    def handle(self, domain, **options):
        csv = options.get('csv')

        couch_counts = _map_doc_types(_get_couchdb_counts(domain))
        sql_counts = _map_doc_types(_get_sql_counts(domain))
        es_counts = _map_doc_types(_get_es_counts(domain))
        all_doc_types = set(couch_counts) | set(sql_counts) | set(es_counts)

        output_rows = []
        for doc_type in sorted(all_doc_types, key=lambda d: d.lower()):
            couch = couch_counts.get(doc_type, '')
            sql = sql_counts.get(doc_type, '')
            es = es_counts.get(doc_type, '')
            output_rows.append((doc_type, couch, sql, es))

        if csv:
            self.output_csv(output_rows)
        else:
            self.output_table(output_rows)

    def output_table(self, output_rows):
        template = "{:<50} | {:<20} | {:<20} | {:<20}"
        self._write_output(template, output_rows)

    def output_csv(self, output_rows):
        template = "{},{},{},{}\n"
        self._write_output(template, output_rows, with_header_divider=False)

    def _write_output(self, template, output_rows, with_header_divider=True, with_color=True):
        self.stdout.write(template.format('Doc Type', 'Couch', 'SQL', 'ES'))
        if with_header_divider:
            self.stdout.write(template.format('-' * 50, *['-' * 20] * 3))
        for doc_type, couch, sql, es in output_rows:
            row_template = template
            if with_color and es and ((couch and couch != es) or (sql and sql != es)):
                row_template = shell_red(template)
            self.stdout.write(row_template.format(doc_type, couch, sql, es))


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

    # for _, doc_ids in SyncLogIDProvider().get_doc_ids(domain):
    #     couch_db_counts['SyncLog'] += len(doc_ids)
    #
    return couch_db_counts


def _get_doc_counts_for_couch_db(couch_db, domain):
    doc_types = couch_db.view(
        "by_domain_doc_type_date/view",
        startkey=[domain],
        endkey=[domain, {}],
        reduce=True,
        group=True,
        group_level=2
    )

    return Counter({row['key'][1]: row['value'] for row in doc_types})


@allow_form_processing_queries()
def _get_sql_counts(domain):
    counter = Counter()
    for model_class, queryset in get_querysets_to_dump(domain, []):
        if model_class in (User, XFormInstanceSQL, CommCareCaseSQL):
            continue  # User is very slow, others we want to break out
        counter[get_model_label(model_class)] += queryset.count()

    counter += _get_sql_forms_by_doc_type(domain)
    counter += _get_sql_cases_by_doc_type(domain)
    return counter


def _get_es_counts(domain):
    counter = Counter()
    for es_query in (es.CaseES, es.FormES, es.UserES, es.AppES, es.LedgerES, es.GroupES):
        counter += _get_index_counts(es_query(), domain)

    return counter


def _get_index_counts(es_query, domain):
    return Counter(
        es_query
        .remove_default_filters()
        .filter(es.filters.term('domain', domain))
        .terms_aggregation('doc_type', 'doc_type')
        .size(0)
        .run()
        .aggregations.doc_type.counts_by_bucket()
    )


def _map_doc_types(counter):
    return Counter({
        DOC_TYPE_MAPPING.get(doc_type, doc_type): count
        for doc_type, count in counter.items()
    })


def _get_sql_forms_by_doc_type(domain):
    counter = Counter()
    for db_alias in get_sql_db_aliases_in_use():
        queryset = XFormInstanceSQL.objects.using(db_alias).filter(domain=domain)
        for doc_type, state in doc_type_to_state.items():
            counter[doc_type] += queryset.filter(state=state).count()

        where_clause = 'state & {0} = {0}'.format(XFormInstanceSQL.DELETED)
        counter['XFormInstance-Deleted'] += queryset.extra(where=[where_clause]).count()

    return counter


def _get_sql_cases_by_doc_type(domain):
    counter = Counter()
    for db_alias in get_sql_db_aliases_in_use():
        queryset = CommCareCaseSQL.objects.using(db_alias).filter(domain=domain)
        counter['CommCareCase'] += queryset.filter(deleted=False).count()
        counter['CommCareCase-Deleted'] += queryset.filter(deleted=True).count()

    return counter
