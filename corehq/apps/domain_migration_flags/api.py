from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.domain_migration_flags.exceptions import DomainMigrationProgressError
from corehq.toggles import DATA_MIGRATION
from corehq.util.quickcache import quickcache
from .models import DomainMigrationProgress, MigrationStatus


def set_migration_started(domain, slug, dry_run=False):
    progress, _ = DomainMigrationProgress.objects.get_or_create(domain=domain, migration_slug=slug)
    if progress.migration_status == MigrationStatus.NOT_STARTED:
        progress.migration_status = MigrationStatus.DRY_RUN if dry_run else MigrationStatus.IN_PROGRESS
        progress.save()
        reset_caches(domain, slug)
    else:
        raise DomainMigrationProgressError(
            'Cannot start a migration that is already in state {}'
            .format(progress.migration_status)
        )


def set_migration_continuing(domain, slug, dry_run=False):
    progress, _ = DomainMigrationProgress.objects.get_or_create(domain=domain, migration_slug=slug)
    if migration_in_progress(domain, slug, True):
        progress.migration_status = MigrationStatus.DRY_RUN if dry_run else MigrationStatus.IN_PROGRESS
        progress.save()
        reset_caches(domain, slug)
    else:
        raise DomainMigrationProgressError(
            'Cannot resume a migration that is in state {}'
            .format(progress.migration_status)
        )


def set_migration_not_started(domain, slug):
    progress, _ = DomainMigrationProgress.objects.get_or_create(domain=domain, migration_slug=slug)
    if migration_in_progress(domain, slug, True):
        progress.migration_status = MigrationStatus.NOT_STARTED
        progress.save()
        reset_caches(domain, slug)
    else:
        raise DomainMigrationProgressError(
            'Cannot abort a migration that is in state {}'
            .format(progress.migration_status)
        )


def set_migration_complete(domain, slug):
    progress, _ = DomainMigrationProgress.objects.get_or_create(domain=domain, migration_slug=slug)

    if progress.migration_status == MigrationStatus.DRY_RUN:
        raise DomainMigrationProgressError("Cannot complete a migration that is in state dry run")

    if progress.migration_status != MigrationStatus.COMPLETE:
        progress.migration_status = MigrationStatus.COMPLETE
        progress.save()
        reset_caches(domain, slug)


def get_migration_complete(domain, slug):
    return get_migration_status(domain, slug) == MigrationStatus.COMPLETE


@quickcache(['domain', 'slug'], skip_arg='strict', timeout=60 * 60, memoize_timeout=60)
def get_migration_status(domain, slug, strict=False):
    try:
        progress = DomainMigrationProgress.objects.get(domain=domain, migration_slug=slug)
        return progress.migration_status
    except DomainMigrationProgress.DoesNotExist:
        return MigrationStatus.NOT_STARTED


def migration_in_progress(domain, slug, include_dry_runs=False):
    status = get_migration_status(domain, slug)
    return status == MigrationStatus.IN_PROGRESS or (include_dry_runs and status == MigrationStatus.DRY_RUN)


@quickcache(['domain'], skip_arg='strict', timeout=60 * 60, memoize_timeout=60)
def any_migrations_in_progress(domain, strict=False):
    """ Checks if any migrations at all are in progress for the domain

    Returns True if there are any migrations in progress where modifications to
    project forms and cases should be prevented.

    This does not include migrations that are marked as dry runs.
    """
    return DATA_MIGRATION.enabled(domain) or DomainMigrationProgress.objects.filter(
        domain=domain, migration_status=MigrationStatus.IN_PROGRESS
    ).exists()


def reset_caches(domain, slug):
    any_migrations_in_progress(domain, strict=True)
    get_migration_status(domain, slug, strict=True)
