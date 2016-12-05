from corehq.apps.couch_sql_migration.couchsqlmigration import commit_migration
from corehq.apps.domain_migration_flags.api import (
    set_migration_started, set_migration_not_started,
    get_migration_status)
from corehq.apps.domain_migration_flags.models import MigrationStatus, DomainMigrationProgress
from corehq.apps.tzmigration.api import set_tz_migration_complete

COUCH_TO_SQL_SLUG = 'couch_to_sql'


def set_couch_sql_migration_started(domain):
    set_migration_started(domain, COUCH_TO_SQL_SLUG)


def set_couch_sql_migration_not_started(domain):
    set_migration_not_started(domain, COUCH_TO_SQL_SLUG)


def couch_sql_migration_in_progress(domain):
    return get_migration_status(domain, COUCH_TO_SQL_SLUG, strict=True) == MigrationStatus.IN_PROGRESS


def set_couch_sql_migration_complete(domain):
    commit_migration(domain)
    # no need to keep this around anymore since state is kept on domain model
    DomainMigrationProgress.objects.filter(domain=domain, migration_slug=COUCH_TO_SQL_SLUG).delete()
    # we get this for free
    set_tz_migration_complete(domain)
