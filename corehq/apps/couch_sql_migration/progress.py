from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings

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
    # no need to keep this around anymore since state is kept on domain model
    DomainMigrationProgress.objects.filter(domain=domain, migration_slug=COUCH_TO_SQL_SLUG).delete()
    # we get this for free
    set_tz_migration_complete(domain)
    _notify_dimagi_users_on_domain(domain)
