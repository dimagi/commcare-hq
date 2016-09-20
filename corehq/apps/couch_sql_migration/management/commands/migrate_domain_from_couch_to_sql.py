from itertools import izip_longest
from optparse import make_option

from django.conf import settings
from django.core.management.base import CommandError, LabelCommand
from sqlalchemy.exc import OperationalError

from corehq.apps.couch_sql_migration.couchsqlmigration import (
    do_couch_to_sql_migration, delete_diff_db, get_diff_db,
    commit_migration)
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.apps.tzmigration.api import set_migration_started, set_migration_not_started, get_migration_status, \
    MigrationStatus, set_migration_complete
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, CaseAccessorSQL
from corehq.form_processor.utils import should_use_sql_backend
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import doc_types, XFormInstance


class Command(LabelCommand):
    args = "<domain>"
    option_list = LabelCommand.option_list + (
        make_option('--MIGRATE', action='store_true', default=False),
        make_option('--COMMIT', action='store_true', default=False),
        make_option('--blow-away', action='store_true', default=False),
        make_option('--stats-short', action='store_true', default=False),
        make_option('--stats-long', action='store_true', default=False),
        make_option('--show-diffs', action='store_true', default=False),
        make_option('--no-input', action='store_true', default=False),
        make_option('--debug', action='store_true', default=False),
    )

    @staticmethod
    def require_only_option(sole_option, options):
        this_command_opts = {'MIGRATE', 'COMMIT', 'blow_away', 'stats', 'show_diffs', 'no_input', 'debug'}
        assert all(not value for key, value in options.items()
                   if key in this_command_opts and key != sole_option)

    def handle_label(self, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError(u'It looks like {} has already been migrated.'.format(domain))

        self.no_input = options.pop('no_input', False)
        self.debug = options.pop('debug', False)
        if self.no_input and not settings.UNIT_TESTING:
            raise CommandError('no-input only allowed for unit testing')

        if options['MIGRATE']:
            self.require_only_option('MIGRATE', options)
            set_migration_started(domain)
            do_couch_to_sql_migration(domain, with_progress=not self.no_input, debug=self.debug)
            self.print_stats(domain, short=options['stats_short'], diffs_only=True)
        if options['blow_away']:
            self.require_only_option('blow_away', options)
            if not self.no_input:
                _confirm(
                    "This will delete all SQL forms and cases for the domain {}. "
                    "Are you sure you want to continue?".format(domain)
                )
            set_migration_not_started(domain)
            _blow_away_migration(domain)
        if options['stats_short'] or options['stats_long']:
            self.print_stats(domain, short=options['stats_short'])
        if options['show_diffs']:
            self.show_diffs(domain)
        if options['COMMIT']:
            self.require_only_option('COMMIT', options)
            assert get_migration_status(domain, strict=True) == MigrationStatus.IN_PROGRESS
            if not self.no_input:
                _confirm(
                    "This will allow convert the domain to use the SQL backend and"
                    "allow new form submissions to be processed. "
                    "Are you sure you want to do this for domain '{}'?".format(domain)
                )
            commit_migration(domain)
            set_migration_complete(domain)

    def show_diffs(self, domain):
        db = get_diff_db(domain)
        for diff in db.get_diffs():
            print '[{}({})] {}'.format(diff.kind, diff.doc_id, diff.json_diff)

    def print_stats(self, domain, short=True, diffs_only=False):
        db = get_diff_db(domain)
        try:
            diff_stats = db.get_diff_stats()
        except OperationalError:
            diff_stats = {}

        has_diffs = False
        for doc_type in doc_types():
            form_ids_in_couch = set(get_form_ids_by_type(domain, doc_type))
            form_ids_in_sql = set(FormAccessorSQL.get_form_ids_in_domain_by_type(domain, doc_type))
            diff_count = diff_stats.pop(doc_type, 0)
            has_diffs |= self._print_status(
                doc_type, form_ids_in_couch, form_ids_in_sql, diff_count, short, diffs_only
            )

        form_ids_in_couch = set(get_doc_ids_in_domain_by_type(
            domain, "XFormInstance-Deleted", XFormInstance.get_db())
        )
        form_ids_in_sql = set(FormAccessorSQL.get_deleted_form_ids_in_domain(domain))
        diff_count = diff_stats.pop("XFormInstance-Deleted", 0)
        has_diffs |= self._print_status(
            "XFormInstance-Deleted", form_ids_in_couch, form_ids_in_sql, diff_count, short, diffs_only
        )

        case_ids_in_couch = set(get_case_ids_in_domain(domain))
        case_ids_in_sql = set(CaseAccessorSQL.get_case_ids_in_domain(domain))
        diff_count = diff_stats.pop("CommCareCase", 0)
        has_diffs |= self._print_status(
            'CommCareCase', case_ids_in_couch, case_ids_in_sql, diff_count, short, diffs_only
        )

        case_ids_in_couch = set(get_doc_ids_in_domain_by_type(
            domain, "CommCareCase-Deleted", XFormInstance.get_db())
        )
        case_ids_in_sql = set(CaseAccessorSQL.get_deleted_case_ids_in_domain(domain))
        diff_count = diff_stats.pop("CommCareCase-Deleted", 0)
        has_diffs |= self._print_status(
            'CommCareCase-Deleted', case_ids_in_couch, case_ids_in_sql, diff_count, short, diffs_only
        )

        if diff_stats:
            for key, count in diff_stats.items():
                has_diffs |= self._print_status(
                    key, set(), set(), count, short, diffs_only
                )

        if diffs_only and not has_diffs:
            print green("No differences found between old and new docs!")

    def _print_status(self, name, ids_in_couch, ids_in_sql, diff_count, short, diffs_only):
        n_couch = len(ids_in_couch)
        n_sql = len(ids_in_sql)
        has_diff = n_couch != n_sql or diff_count

        if diffs_only and not has_diff:
            return False

        def _highlight(text):
            return red(text) if has_diff else text

        row = "{:^40} | {:^40}"
        doc_count_row = row.format(n_couch, n_sql)
        header = ((82 - len(name)) / 2) * '_'

        print '\n{} {} {}'.format(header, name, header)
        print row.format('Couch', 'SQL')
        print _highlight(doc_count_row)
        if diff_count:
            print _highlight("{:^83}".format('{} diffs'.format(diff_count)))

        if not short:
            if ids_in_couch ^ ids_in_sql:
                couch_only = list(ids_in_couch - ids_in_sql)
                sql_only = list(ids_in_sql - ids_in_couch)
                for couch, sql in izip_longest(couch_only, sql_only):
                    print row.format(couch or '', sql or '')

        return True


def _confirm(message):
    if raw_input(
            '{} [y/n]'.format(message)
    ).lower() == 'y':
        return
    else:
        raise CommandError('abort')


def _blow_away_migration(domain):
    assert not should_use_sql_backend(domain)
    delete_diff_db(domain)

    for doc_type in doc_types():
        sql_form_ids = FormAccessorSQL.get_form_ids_in_domain_by_type(domain, doc_type)
        FormAccessorSQL.hard_delete_forms(domain, sql_form_ids, delete_attachments=False)

    sql_form_ids = FormAccessorSQL.get_deleted_form_ids_in_domain(domain)
    FormAccessorSQL.hard_delete_forms(domain, sql_form_ids, delete_attachments=False)

    sql_case_ids = CaseAccessorSQL.get_case_ids_in_domain(domain)
    CaseAccessorSQL.hard_delete_cases(domain, sql_case_ids)

    sql_case_ids = CaseAccessorSQL.get_deleted_case_ids_in_domain(domain)
    CaseAccessorSQL.hard_delete_cases(domain, sql_case_ids)


def _color_template(color_code):
    def inner(text):
        return "\033[%sm%s\033[0m" % (color_code, text)
    return inner

red = _color_template('31')
green = _color_template('32')
