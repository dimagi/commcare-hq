from __future__ import absolute_import
from __future__ import unicode_literals
from six.moves import zip_longest

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.data_pipeline_audit.dbacessors import get_es_user_ids, get_es_form_ids, get_primary_db_form_ids, \
    get_primary_db_case_ids, get_es_case_ids
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_class
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_ids_by_domain, get_mobile_user_ids
from corehq.apps.users.models import CommCareUser
from corehq.util.markup import SimpleTableWriter, CSVRowFormatter, TableRowFormatter
from couchforms.models import doc_types


class Command(BaseCommand):
    help = "Print doc IDs that are in the primary DB but not in ES. Use in conjunction with 'raw_doc' view."

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('doc_type')
        parser.add_argument('--csv', action='store_true', default=False, dest='csv',
                            help='Write output in CSV format.')

    def handle(self, domain, doc_type, **options):
        csv = options.get('csv')

        handlers = {
            'CommCareCase': compare_cases,
            'CommCareCase-Deleted': compare_cases,
            'CommCareUser': _compare_users,
            'CommCareUser-Deleted': _compare_users,
            'WebUser': _compare_users,
        }
        handlers.update({doc_type: compare_xforms for doc_type in doc_types()})
        try:
            primary_only, es_only = handlers[doc_type](domain, doc_type)
        except KeyError:
            raise CommandError('Unsupported doc type. Use on of: {}'.format(', '.join(handlers)))

        if csv:
            row_formatter = CSVRowFormatter()
        else:
            row_formatter = TableRowFormatter([50, 50])

        writer = SimpleTableWriter(self.stdout, row_formatter)
        writer.write_table(
            ['Only in Primary', 'Only in ES'],
            zip_longest(primary_only, es_only, fillvalue='')
        )


def compare_cases(domain, doc_type):
    return _get_diffs(
        get_primary_db_case_ids(domain, doc_type),
        get_es_case_ids(domain, doc_type)
    )


def compare_xforms(domain, doc_type):
    return _get_diffs(
        get_primary_db_form_ids(domain, doc_type),
        get_es_form_ids(domain, doc_type)
    )


def _compare_users(domain, doc_type):
    include_web_users = doc_type == 'WebUser'
    if not include_web_users and 'Deleted' in doc_type:
        # deleted users = all users - non-deleted users
        all_mobile_user_ids = set(get_doc_ids_in_domain_by_class(domain, CommCareUser))
        non_deleted_mobile_user_ids = get_mobile_user_ids(domain)
        couch_count = all_mobile_user_ids - non_deleted_mobile_user_ids
    else:
        couch_count = set(get_all_user_ids_by_domain(
            domain,
            include_web_users=include_web_users,
            include_mobile_users=not include_web_users)
        )
    return _get_diffs(
        couch_count,
        get_es_user_ids(domain, doc_type)
    )


def _get_diffs(primary_ids, es_ids):
    return primary_ids - es_ids, es_ids - primary_ids
