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
        'DomainInvitation',
        'DomainRemovalRecord',
        'OrgRemovalRecord',
    )
)


def get_migrator_by_slug(slug):
    return Migrator.instances[slug]


def get_migrator_slugs():
    return sorted(Migrator.instances.keys())
