from __future__ import absolute_import
from __future__ import unicode_literals

import logging
import os
from io import open

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.domain.dbaccessors import get_doc_ids_in_domain_by_type
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import clear_local_domain_sql_backend_override
from corehq.util.markup import SimpleTableWriter, TableRowFormatter
from couchforms.dbaccessors import get_form_ids_by_type
from couchforms.models import XFormInstance, doc_types

from ...couchsqlmigration import do_couch_to_sql_migration, get_diff_db, setup_logging
from ...progress import (
    couch_sql_migration_in_progress,
    set_couch_sql_migration_complete,
    set_couch_sql_migration_not_started,
    set_couch_sql_migration_started,
)
from .migrate_domain_from_couch_to_sql import blow_away_migration

log = logging.getLogger(__name__)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--strict', action='store_true', default=False,
                            help="Abort domain migration even for diffs in deleted doc types")
        parser.add_argument('--log-dir', help="""
            Directory for couch2sql logs, which are not written if this is not
            provided. Standard HQ logs will be used regardless of this setting.
        """)

    def handle(self, path, **options):
        self.strict = options['strict']
        setup_logging(options['log_dir'])

        if not os.path.isfile(path):
            raise CommandError("Couldn't locate domain list: {}".format(path))

        with open(path, 'r', encoding='utf-8') as f:
            domains = [name.strip() for name in f.readlines() if name.strip()]

        failed = []
        log.info("Processing {} domains\n".format(len(domains)))
        for domain in domains:
            try:
                success, reason = self.migrate_domain(domain)
                if not success:
                    failed.append((domain, reason))
            except Exception as err:
                log.exception("Error migrating domain %s", domain)
                self.abort(domain)
                failed.append((domain, err))

        if failed:
            log.error("Errors:\n" + "\n".join(
                ["{}: {}".format(domain, exc) for domain, exc in failed]))
        else:
            log.info("All migrations successful!")

    def migrate_domain(self, domain):
        if should_use_sql_backend(domain):
            log.error("{} already on the SQL backend\n".format(domain))
            return True, None

        if couch_sql_migration_in_progress(domain, include_dry_runs=True):
            log.error("{} migration is already in progress\n".format(domain))
            return False, "in progress"

        set_couch_sql_migration_started(domain)

        do_couch_to_sql_migration(domain, with_progress=False, debug=False)

        stats = get_diff_stats(domain, self.strict)
        if stats:
            preamble = "Migration has diffs: {}".format(domain)
            log.error(format_diff_stats(stats, preamble))
            self.abort(domain)
            return False, "has diffs"

        assert couch_sql_migration_in_progress(domain)
        set_couch_sql_migration_complete(domain)
        log.info("Domain migrated: {}\n".format(domain))
        return True, None

    def abort(self, domain):
        set_couch_sql_migration_not_started(domain)
        clear_local_domain_sql_backend_override(domain)
        blow_away_migration(domain)


def get_diff_stats(domain, strict=True):
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

    if strict:
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


def format_diff_stats(stats, preamble=None):
    lines = []
    if stats:
        if preamble:
            lines.append(preamble)

        class stream:
            write = lines.append

        writer = SimpleTableWriter(stream, TableRowFormatter([30, 10, 10, 10, 10]))
        writer.write_table(
            ['Doc Type', '# Couch', '# SQL', '# Diffs', '# Docs with Diffs'],
            [(doc_type,) + stat for doc_type, stat in stats.items()],
        )
    return "\n".join(lines)
