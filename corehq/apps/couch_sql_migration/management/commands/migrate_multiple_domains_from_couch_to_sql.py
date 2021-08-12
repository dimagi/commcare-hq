import logging
import os

import attr

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
    get_couch_sql_migration_status,
    set_couch_sql_migration_complete,
    set_couch_sql_migration_not_started,
    set_couch_sql_migration_started,
)
from ...statedb import open_state_db
from .migrate_domain_from_couch_to_sql import (
    blow_away_migration,
    unfinish_couch_sql_migration,
)

log = logging.getLogger(__name__)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domains',
            help="Path to file with one domain name per line OR a colon-"
                 "delimited list of domain names.")
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
            help="Do live migration. Leave in unfinished state if there are "
                 "unpatchable diffs, otherwise patch, finish and commit.")
        parser.add_argument('--resume', action='store_true', default=False,
            help="Resume previously started (live) migration. This should "
                 "only be used when it is known that no other migration "
                 "commands are running on the given domain(s).")

    def handle(self, domains, state_dir, **options):
        self.strict = options['strict']
        self.live_migrate = options["live"]
        self.resume = options["resume"]
        if self.resume and not self.live_migrate:
            raise CommandError("--resume can only be used with --live")

        domains = list_domains(domains)
        failed = []
        log.info("Processing {} domains\n".format(len(domains)))
        for domain in domains:
            setup_logging(state_dir, f"migrate-{domain}")
            try:
                self.migrate_domain(domain, state_dir)
            except CleanBreak:
                failed.append((domain, "stopped by operator"))
                break
            except Incomplete as err:
                log.error("Incomplete migration of %s: %s\n", domain, err)
                failed.append((domain, str(err)))
            except Exception as err:
                log.exception("Error migrating domain %s", domain)
                if not self.live_migrate:
                    self.abort(domain, state_dir)
                failed.append((domain, str(err)))
            except BaseException as err:
                log.exception("Fatal error migrating domain %s", domain)
                failed.append((domain, str(err) or type(err).__name__))
                break
            finally:
                print("")

        if failed:
            log.error("Errors:\n" + "\n".join(
                ["{}: {}".format(domain, exc) for domain, exc in failed]))
        else:
            log.info("All migrations successful!")

    def migrate_domain(self, domain, state_dir):
        if should_use_sql_backend(domain):
            log.info("{} already on the SQL backend\n".format(domain))
            return

        if couch_sql_migration_in_progress(domain, include_dry_runs=True):
            if not self.resume:
                raise Incomplete("migration is in progress")

        set_couch_sql_migration_started(domain, self.live_migrate)
        try:
            do_couch_to_sql_migration(
                domain,
                state_dir,
                with_progress=self.live_migrate,
                live_migrate=self.live_migrate,
            )
        except MigrationRestricted as err:
            set_couch_sql_migration_not_started(domain)
            raise Incomplete(f"migration restricted: {err}")

        if self.live_migrate:
            try:
                self.finish_live_migration_if_possible(domain, state_dir)
            except Incomplete as err:
                unfinish_couch_sql_migration(domain, state_dir)
                raise err
        elif self.has_diffs(domain, state_dir):
            self.abort(domain, state_dir)
            raise Incomplete("has diffs")

        assert couch_sql_migration_in_progress(domain)
        set_couch_sql_migration_complete(domain)
        log.info(f"Domain migrated: {domain}\n")

    def finish_live_migration_if_possible(self, domain, state_dir):
        log.info(f"Finishing {domain} migration")
        set_couch_sql_migration_started(domain)
        do_couch_to_sql_migration(domain, state_dir)  # --finish
        stats = get_diff_stats(domain, state_dir, self.strict)
        if stats:
            if any(s.pending for s in stats.values()):
                log_stats(domain, stats)
                raise Incomplete("has pending diffs or missing docs")
            if "CommCareCase" not in stats:
                log_stats(domain, stats)
                raise Incomplete("has unpatchable diffs")
            assert stats["CommCareCase"].patchable, stats
            log.info(f"Patching {domain} migration")
            do_couch_to_sql_migration(domain, state_dir, case_diff="patch")
            if self.has_diffs(domain, state_dir, resume=True):
                raise Incomplete("has unpatchable or pending diffs")
        log_stats(domain, get_diff_stats(
            domain, state_dir, self.strict, resume=True, verbose=True))

    def has_diffs(self, domain, state_dir, resume=False):
        stats = get_diff_stats(domain, state_dir, self.strict, resume)
        if stats:
            log_stats(domain, stats)
        return bool(stats)

    def abort(self, domain, state_dir):
        set_couch_sql_migration_not_started(domain)
        clear_local_domain_sql_backend_override(domain)
        blow_away_migration(domain, state_dir)


def list_domains(domains):
    if ":" in domains:
        return [d for d in domains.split(":") if d]
    if not os.path.isfile(domains):
        raise CommandError(f"Couldn't locate domain list: {domains}")
    with open(domains, 'r', encoding='utf-8') as f:
        return [d.strip() for d in f.readlines() if d.strip()]


def get_diff_stats(domain, state_dir, strict, resume=False, verbose=False):
    DELETED_CASE = "CommCareCase-Deleted"
    find_missing_docs(domain, state_dir, resume=resume, progress=False)
    stats = {}
    with open_state_db(domain, state_dir) as statedb:
        for doc_type, counts in sorted(statedb.get_doc_counts().items()):
            if doc_type == DELETED_CASE and not (
                    strict or counts.missing or verbose):
                continue
            if counts.diffs or counts.changes or counts.missing or (
                    verbose and counts.total):
                stats[doc_type] = DiffStats(counts)
        pending = statedb.count_undiffed_cases()
        if pending:
            if "CommCareCase" not in stats:
                stats["CommCareCase"] = DiffStats(pending=pending)
            else:
                stats["CommCareCase"].pending = pending
    return stats


def log_stats(domain, stats):
    status = get_couch_sql_migration_status(domain)
    header = f"Couch to SQL migration status for {domain}: {status}"
    log.info(format_diff_stats(stats, header))


def format_diff_stats(stats, header=None):
    lines = []
    if stats:
        if header:
            lines.append(header)

        class stream:
            write = lines.append

        writer = SimpleTableWriter(stream, TableRowFormatter([30, 7, 7, 7, 7]))
        writer.write_table(
            ['Doc Type', 'Docs', 'Diffs', "Missing", "Changes"],
            [(doc_type,) + stat.columns for doc_type, stat in stats.items()],
        )
    return "\n".join(lines)


@attr.s
class DiffStats:
    counts = attr.ib(default=None)
    pending = attr.ib(default=0)

    @property
    def columns(self):
        pending = f"{self.pending} pending" if self.pending else ""
        counts = self.counts
        if not counts:
            return "?", "?", "?", pending
        changes = counts.changes
        if pending:
            changes = f"{changes} + {pending}" if changes else pending
        return counts.total, counts.diffs, counts.missing, changes

    @property
    def patchable(self):
        counts = self.counts
        return counts and (counts.missing + counts.diffs + counts.changes)


class Incomplete(Exception):
    pass
