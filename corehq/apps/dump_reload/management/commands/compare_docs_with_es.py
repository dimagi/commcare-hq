from django.core.management.base import BaseCommand, CommandError

from corehq.apps import es
from corehq.apps.dump_reload.sql.dump import allow_form_processing_queries
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_ids_by_domain
from corehq.form_processor.backends.sql.dbaccessors import doc_type_to_state
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.sql_db.config import get_sql_db_aliases_in_use


class Command(BaseCommand):
    help = "Print doc IDs that are in the primary DB but not in ES. Use in conjunction with 'raw_doc' view."
    args = '<domain> <doc_type>'

    def handle(self, domain, doc_type, **options):
        if not should_use_sql_backend(domain):
            raise CommandError('Only SQL backends currently supported')

        handlers = {
            'xforminstance': _compare_xforms,
            'commcarecase': _compare_cases,
            'commcareuser': _compare_mobile_users,
        }
        try:
            diff = handlers[doc_type.lower()](domain, doc_type)
        except KeyError:
            raise CommandError('Unsupported doc type. Use on of: {}'.format(', '.join(handlers)))

        self.stdout.write('{} "{}" docs are missing from ES'.format(len(diff), doc_type))
        for doc_id in diff:
            self.stdout.write(doc_id)


@allow_form_processing_queries()
def _compare_cases(domain, doc_type):
    sql_ids = set()
    for db_alias in get_sql_db_aliases_in_use():
        queryset = CommCareCaseSQL.objects.using(db_alias) \
            .filter(domain=domain, deleted=False).values_list('case_id', flat=True)
        sql_ids.update(list(queryset))

    es_ids = set(
        es.CaseES()
        .remove_default_filters()
        .filter(es.filters.term('domain', domain))
        .get_ids()
    )

    return sql_ids - es_ids


@allow_form_processing_queries()
def _compare_xforms(domain, doc_type):
    sql_ids = set()
    state = doc_type_to_state[doc_type]
    for db_alias in get_sql_db_aliases_in_use():
        queryset = XFormInstanceSQL.objects.using(db_alias) \
            .filter(domain=domain, state=state).values_list('form_id', flat=True)
        sql_ids.update(list(queryset))

    es_ids = set(
        es.FormES()
        .remove_default_filters()
        .filter(es.filters.term('domain', domain))
        .filter(es.filters.term('doc_type', doc_type.lower()))
        .get_ids()
    )

    return sql_ids - es_ids


def _compare_mobile_users(domain, doc_type):
    couch_ids = set(get_all_user_ids_by_domain(domain, include_web_users=False))

    es_ids = set(
        es.UserES()
        .remove_default_filter('active')
        .filter(es.filters.term('domain', domain))
        .get_ids()
    )

    return couch_ids - es_ids
