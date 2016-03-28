from django.conf import settings
from corehq.doctypemigrations.migrator import Migrator

users_migration = Migrator(
    slug='user_db_migration',
    source_db_name=None,
    target_db_name=settings.NEW_USERS_GROUPS_DB,
    doc_types=(
        'Group',
        'DeleteGroupRecord',
        'UserRole',
        'AdminUserRole',
        'CommCareUser',
        'WebUser',
        'Invitation',
        'DomainRemovalRecord',
        'OrgRemovalRecord',
    )
)

fixtures_migration = Migrator(
    slug='fixtures',
    source_db_name=None,
    target_db_name=settings.NEW_FIXTURES_DB,
    doc_types=(
        'FixtureDataType',
        'FixtureDataItem',
        'FixtureOwnership',
    )
)

domains_migration = Migrator(
    slug='domains',
    source_db_name=None,
    target_db_name=settings.NEW_DOMAINS_DB,
    doc_types=('Domain',)
)

apps_migration = Migrator(
    slug='apps',
    source_db_name=None,
    target_db_name=settings.NEW_APPS_DB,
    doc_types=(
        'Application',
        'ApplicationBase',
        'CareplanConfig',
        'DeleteApplicationRecord',
        'DeleteFormRecord',
        'DeleteModuleRecord',
        'RemoteApp',
        'SavedAppBuild',
        'VersionedDoc',
    )
)


def get_migrator_by_slug(slug):
    return Migrator.instances[slug]


def get_migrator_slugs():
    return sorted(Migrator.instances.keys())
