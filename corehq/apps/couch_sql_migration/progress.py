from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf import settings

from corehq.apps.domain_migration_flags.api import (
    MigrationStatus,
    get_migration_status,
    set_migration_started,
    set_migration_not_started,
    set_migration_complete,
    migration_in_progress,
)
from corehq.apps.tzmigration.api import set_tz_migration_complete

COUCH_TO_SQL_SLUG = 'couch_to_sql'


def get_couch_sql_migration_status(domain):
    return get_migration_status(domain, COUCH_TO_SQL_SLUG)


def set_couch_sql_migration_started(domain, live_migrate=False):
    if not live_migrate:
        # allow live (dry run) migration to be completed
        if get_couch_sql_migration_status(domain) == MigrationStatus.DRY_RUN:
            # avoid "Cannot start a migration that is already in state dry_run"
            set_couch_sql_migration_not_started(domain)
    set_migration_started(domain, COUCH_TO_SQL_SLUG, dry_run=live_migrate)


def set_couch_sql_migration_not_started(domain):
    set_migration_not_started(domain, COUCH_TO_SQL_SLUG)


def couch_sql_migration_in_progress(domain, include_dry_runs=True):
    return migration_in_progress(domain, COUCH_TO_SQL_SLUG, include_dry_runs)


def _notify_dimagi_users_on_domain(domain):
    from corehq.apps.users.models import WebUser
    from corehq.apps.hqwebapp.tasks import send_mail_async
    recipients = [
        user.get_email() for user in WebUser.by_domain(domain) if user.is_dimagi
    ]

    subject = 'CommCare HQ project migrated to the scale backend.'.format(domain)
    message = """
    The CommCare HQ project "{}" has been migrated to the scale backend.

    You should not notice anything different but if you do please report a bug.
    """.format(domain)
    send_mail_async.delay(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipients
    )


def set_couch_sql_migration_complete(domain):
    from corehq.apps.couch_sql_migration.couchsqlmigration import commit_migration
    commit_migration(domain)
    set_migration_complete(domain, COUCH_TO_SQL_SLUG)
    # we get this for free
    set_tz_migration_complete(domain)
    _notify_dimagi_users_on_domain(domain)
