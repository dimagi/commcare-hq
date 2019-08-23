from __future__ import absolute_import, unicode_literals

from django.template import Template

from corehq.apps.sms.models import MigrationStatus
from corehq.util.django_migrations import skip_on_fresh_install

EXCEPTION_MESSAGE = Template("""

*** Halting migrate command because one or more messaging postgres migrations
have not yet completed.

In order to continue, switch into your code root (and virtual environment if
you have one), and do the following:

git fetch origin
git checkout {{ tag_name }}
git submodule update --init --recursive
find . -name "*.pyc" -delete # (linux command to delete .pyc files - adjust appropriately for your platform)
{% for command in commands %}python manage.py {{ command }}
{% endfor %}

You can then checkout the branch you were previously on (master, presumably),
update submodules, clean *.pyc files, and run python manage.py migrate normally.

NOTE: If you are seeing this on a fresh install of CommCareHQ, then you can
ignore the above. Instead, the first time you run migrate, run it with the
following command (this command assumes a linux environment - for other platforms
you just need to run python manage.py migrate with a temporary environment
variable CCHQ_IS_FRESH_INSTALL set to 1):
    env CCHQ_IS_FRESH_INSTALL=1 python manage.py migrate
""")


class MigrationInfo(object):

    def __init__(self, migration_names, tag_name, commands):
        """
        migration_names - A list of MigrationStatus.MIGRATION_* constants
                          that will be checked. If any of those migrations
                          have not run then a MigrationException with the
                          EXCEPTION_MESSAGE will be raised.
        tag_name - The name of the git tag which should be checked out to
                   run the management commands.
        commands - The list of management commands that need to be run in order
                   to complete the migrations referenced by migration_names.
        """
        self.migration_names = migration_names
        self.context = {
            'tag_name': tag_name,
            'commands': commands,
        }


class MigrationException(Exception):
    pass


@skip_on_fresh_install
def assert_messaging_migration_complete(info):
    migrations_have_not_run = any(
        [not MigrationStatus.has_migration_completed(name) for name in info.migration_names]
    )
    if migrations_have_not_run:
        raise MigrationException(EXCEPTION_MESSAGE.render(info.context))


def assert_backend_migration_complete(apps, schema_editor):
    assert_messaging_migration_complete(
        MigrationInfo(
            [MigrationStatus.MIGRATION_BACKEND, MigrationStatus.MIGRATION_BACKEND_MAP],
            'backend-messaging-migration',
            ['migrate_backends_to_sql', 'migrate_backend_mappings_to_sql']
        )
    )


def assert_domain_default_backend_migration_complete(apps, schema_editor):
    assert_messaging_migration_complete(
        MigrationInfo(
            [MigrationStatus.MIGRATION_DOMAIN_DEFAULT_BACKEND],
            'domain-default-backend-messaging-migration',
            ['migrate_domain_default_backend']
        )
    )


def assert_log_migration_complete(apps, schema_editor):
    assert_messaging_migration_complete(
        MigrationInfo(
            [MigrationStatus.MIGRATION_LOGS],
            'logs-messaging-migration',
            ['migrate_logs_to_sql']
        )
    )


def assert_phone_number_migration_complete(apps, schema_editor):
    assert_messaging_migration_complete(
        MigrationInfo(
            [MigrationStatus.MIGRATION_PHONE_NUMBERS],
            'phone-number-messaging-migration',
            ['migrate_phone_numbers_to_sql']
        )
    )


def assert_keyword_migration_complete(apps, schema_editor):
    assert_messaging_migration_complete(
        MigrationInfo(
            [MigrationStatus.MIGRATION_KEYWORDS],
            'keyword-messaging-migration',
            ['migrate_keywords']
        )
    )
