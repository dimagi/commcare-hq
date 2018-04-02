from __future__ import absolute_import
from __future__ import unicode_literals
import os
import traceback

from django.core.management.base import CommandError, BaseCommand

from corehq.apps.couch_sql_migration.couchsqlmigration import (
    do_couch_to_sql_migration, get_diff_db)
from corehq.apps.couch_sql_migration.management.commands.migrate_domain_from_couch_to_sql import _blow_away_migration
from corehq.apps.couch_sql_migration.progress import (
    set_couch_sql_migration_started, couch_sql_migration_in_progress,
    set_couch_sql_migration_not_started, set_couch_sql_migration_complete
)
from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL, CaseAccessorSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import clear_local_domain_sql_backend_override
from corehq.util.log import with_progress_bar
from corehq.util.markup import shell_green, SimpleTableWriter, TableRowFormatter
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import doc_types, XFormInstance


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--strict', action='store_true', default=False,
                            help="Abort domain migration even for diffs in deleted doc types")

    def handle(self, path, **options):
        with_traceback = options['traceback']
        self.strict = options['strict']

        if not os.path.isfile(path):
            raise CommandError("Couldn't locate domain list: {}".format(path))

        self.stdout.ending = "\n"
        self.stderr.ending = "\n"
        with open(path, 'r') as f:
            domains = [name.strip() for name in f.readlines()]

        self.stdout.write("Processing {} domains".format(len(domains)))
        for domain in with_progress_bar(domains, oneline=False):
            try:
                self.migrate_domain(domain)
            except Exception as e:
                if with_traceback:
                    traceback.print_exc()
                self.stderr.write("Error migrating domain {}: {}".format(domain, e))
                self.abort(domain)

    def migrate_domain(self, domain):
        if should_use_sql_backend(domain):
            self.stderr.write("{} already on the SQL backend".format(domain))
            return

        set_couch_sql_migration_started(domain)

        do_couch_to_sql_migration(domain, with_progress=False, debug=False)
        stats = self.get_diff_stats(domain)
        if stats:
            self.stderr.write("Migration has diffs, aborting for domain {}".format(domain))
            self.abort(domain)
            writer = SimpleTableWriter(self.stdout, TableRowFormatter([50, 10, 10, 10]))
            writer.write_table(['Doc Type', '# Couch', '# SQL', '# Diffs', '# Docs with Diffs'], [
                (doc_type,) + stat for doc_type, stat in stats.items()
            ])
        else:
            assert couch_sql_migration_in_progress(domain)
            set_couch_sql_migration_complete(domain)
            self.stdout.write(shell_green("Domain migrated: {}".format(domain)))

    def get_diff_stats(self, domain):
        db = get_diff_db(domain)
        diff_stats = db.get_diff_stats()

        stats = {}

        def _update_stats(doc_type, couch_count, sql_count):
            diff_count, num_docs_with_diffs = diff_stats.pop(doc_type, (0, 0))
            if diff_count or couch_count != sql_count:
                stats[doc_type] = (couch_count, sql_count, diff_count, num_docs_with_diffs)

        for doc_type in doc_types():
            form_ids_in_couch = len(set(get_form_ids_by_type(domain, doc_type)))
            form_ids_in_sql = len(set(FormAccessorSQL.get_form_ids_in_domain_by_type(domain, doc_type)))
            _update_stats(doc_type, form_ids_in_couch, form_ids_in_sql)

        form_ids_in_couch = len(set(get_doc_ids_in_domain_by_type(
            domain, "XFormInstance-Deleted", XFormInstance.get_db())
        ))
        form_ids_in_sql = len(set(FormAccessorSQL.get_deleted_form_ids_in_domain(domain)))
        _update_stats("XFormInstance-Deleted", form_ids_in_couch, form_ids_in_sql)

        case_ids_in_couch = len(set(get_case_ids_in_domain(domain)))
        case_ids_in_sql = len(set(CaseAccessorSQL.get_case_ids_in_domain(domain)))
        _update_stats("CommCareCase", case_ids_in_couch, case_ids_in_sql)

        if self.strict:
            # only care about these in strict mode
            case_ids_in_couch = len(set(get_doc_ids_in_domain_by_type(
                domain, "CommCareCase-Deleted", XFormInstance.get_db())
            ))
            case_ids_in_sql = len(set(CaseAccessorSQL.get_deleted_case_ids_in_domain(domain)))
            _update_stats("CommCareCase-Deleted", case_ids_in_couch, case_ids_in_sql)

        if diff_stats:
            for key in diff_stats.keys():
                _update_stats(key, 0, 0)

        return stats

    def abort(self, domain):
        set_couch_sql_migration_not_started(domain)
        clear_local_domain_sql_backend_override(domain)
        _blow_away_migration(domain)
