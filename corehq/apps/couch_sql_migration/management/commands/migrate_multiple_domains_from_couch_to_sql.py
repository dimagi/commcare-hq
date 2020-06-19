import logging
import os

from django.core.management.base import BaseCommand, CommandError

from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.utils.general import (
    clear_local_domain_sql_backend_override,
)
from corehq.util.markup import SimpleTableWriter, TableRowFormatter

from ...couchsqlmigration import (
    CleanBreak,
    MigrationRestricted,
    do_couch_to_sql_migration,
    setup_logging,
)
from ...missingdocs import find_missing_docs
from ...progress import (
    couch_sql_migration_in_progress,
    set_couch_sql_migration_complete,
    set_couch_sql_migration_not_started,
    set_couch_sql_migration_started,
)
from ...statedb import open_state_db
from .migrate_domain_from_couch_to_sql import blow_away_migration

log = logging.getLogger(__name__)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--state-dir',
            default=os.environ.get("CCHQ_MIGRATION_STATE_DIR"),
            required="CCHQ_MIGRATION_STATE_DIR" not in os.environ,
            help="""
                Directory for couch2sql logs and migration state. This must not
                reside on an NFS volume for migration state consistency.
                Can be set in environment: CCHQ_MIGRATION_STATE_DIR
            """)
        parser.add_argument('--strict', action='store_true', default=False,
            help="Abort domain migration even for diffs in deleted doc types")
        parser.add_argument('--live', action='store_true', default=False,
            help="Do live migration, leave in live/unfinished state.")

    def handle(self, path, state_dir, **options):
        self.strict = options['strict']
        self.live_migrate = options["live"]

        if not os.path.isfile(path):
            raise CommandError("Couldn't locate domain list: {}".format(path))

        with open(path, 'r', encoding='utf-8') as f:
            domains = [name.strip() for name in f.readlines() if name.strip()]

        failed = []
        log.info("Processing {} domains\n".format(len(domains)))
        for domain in domains:
            setup_logging(state_dir, f"migrate-{domain}")
            try:
                success, reason = self.migrate_domain(domain, state_dir)
                if not success:
                    failed.append((domain, reason))
            except CleanBreak:
                failed.append((domain, "stopped by operator"))
                break
            except Exception as err:
                log.exception("Error migrating domain %s", domain)
                if not self.live_migrate:
                    self.abort(domain, state_dir)
                failed.append((domain, err))

        if failed:
            log.error("Errors:\n" + "\n".join(
                ["{}: {}".format(domain, exc) for domain, exc in failed]))
        else:
            log.info("All migrations successful!")

    def migrate_domain(self, domain, state_dir):
        if should_use_sql_backend(domain):
            log.info("{} already on the SQL backend\n".format(domain))
            return True, None

        if couch_sql_migration_in_progress(domain, include_dry_runs=True):
            log.error("{} migration is in progress\n".format(domain))
            return False, "in progress"

        set_couch_sql_migration_started(domain, self.live_migrate)
        try:
            do_couch_to_sql_migration(
                domain,
                state_dir,
                with_progress=self.live_migrate,
                live_migrate=self.live_migrate,
            )
        except MigrationRestricted as err:
            log.error("migration restricted: %s", err)
            set_couch_sql_migration_not_started(domain)
            return False, str(err)

        has_diffs = self.check_diffs(domain, state_dir)
        if self.live_migrate:
            return True, None
        if has_diffs:
            self.abort(domain, state_dir)
            return False, "has diffs"

        assert couch_sql_migration_in_progress(domain)
        set_couch_sql_migration_complete(domain)
        log.info("Domain migrated: {}\n".format(domain))
        return True, None

    def check_diffs(self, domain, state_dir):
        stats = get_diff_stats(domain, state_dir, self.strict)
        if stats:
            header = "Migration has diffs: {}".format(domain)
            log.error(format_diff_stats(stats, header))
        return bool(stats)

    def abort(self, domain, state_dir):
        set_couch_sql_migration_not_started(domain)
        clear_local_domain_sql_backend_override(domain)
        blow_away_migration(domain, state_dir)


def get_diff_stats(domain, state_dir, strict=True):
    find_missing_docs(domain, state_dir, resume=False, progress=False)
    statedb = open_state_db(domain, state_dir)
    stats = {}
    for doc_type, counts in sorted(statedb.get_doc_counts().items()):
        if not strict and doc_type == "CommCareCase-Deleted":
            continue
        if counts.diffs or counts.changes or counts.missing:
            couch_count = counts.total
            sql_count = counts.total - counts.missing
            stats[doc_type] = (couch_count, sql_count, counts.diffs + counts.changes)
    if "CommCareCase" not in stats:
        pending = statedb.count_undiffed_cases()
        if pending:
            stats["CommCareCase"] = ("?", "?", f"{pending} diffs pending")
    return stats


def format_diff_stats(stats, header=None):
    lines = []
    if stats:
        if header:
            lines.append(header)

        class stream:
            write = lines.append

        writer = SimpleTableWriter(stream, TableRowFormatter([30, 10, 10, 10]))
        writer.write_table(
            ['Doc Type', '# Couch', '# SQL', '# Docs with Diffs'],
            [(doc_type,) + stat for doc_type, stat in stats.items()],
        )
    return "\n".join(lines)
