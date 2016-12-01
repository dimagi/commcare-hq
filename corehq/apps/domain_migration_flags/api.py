from corehq.apps.domain_migration_flags.exceptions import DomainMigrationProgressError
from corehq.util.quickcache import skippable_quickcache
from models import DomainMigrationProgress, MigrationStatus


def set_migration_started(domain, slug):
    progress, _ = DomainMigrationProgress.objects.get_or_create(domain=domain, migration_slug=slug)
    if progress.migration_status == MigrationStatus.NOT_STARTED:
        progress.migration_status = MigrationStatus.IN_PROGRESS
        progress.save()
        # reset cache
        get_migration_status(domain, slug, strict=True)
    else:
        raise DomainMigrationProgressError(
            'Cannot start a migration that is already in state {}'
            .format(progress.migration_status)
        )


def set_migration_not_started(domain, slug):
    progress, _ = DomainMigrationProgress.objects.get_or_create(domain=domain, migration_slug=slug)
    if progress.migration_status == MigrationStatus.IN_PROGRESS:
        progress.migration_status = MigrationStatus.NOT_STARTED
        progress.save()
        # reset cache
        get_migration_status(domain, slug, strict=True)
    else:
        raise DomainMigrationProgressError(
            'Cannot abort a migration that is in state {}'
            .format(progress.migration_status)
        )


def set_migration_complete(domain, slug):
    progress, _ = DomainMigrationProgress.objects.get_or_create(domain=domain, migration_slug=slug)
    if progress.migration_status != MigrationStatus.COMPLETE:
        progress.migration_status = MigrationStatus.COMPLETE
        progress.save()
        # reset cache
        get_migration_status(domain, slug, strict=True)


def get_migration_complete(domain, slug):
    return get_migration_status(domain, slug) == MigrationStatus.COMPLETE


@skippable_quickcache(['domain', 'slug'], skip_arg='strict')
def get_migration_status(domain, slug, strict=False):
    progress, _ = DomainMigrationProgress.objects.get_or_create(domain=domain, migration_slug=slug)
    return progress.migration_status


def migration_in_progress(domain, slug):
    return get_migration_status(domain, slug) == MigrationStatus.IN_PROGRESS
