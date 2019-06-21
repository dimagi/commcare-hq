from __future__ import absolute_import
from __future__ import unicode_literals

import logging
from collections import defaultdict
from datetime import datetime

from django.db.models import Q

from corehq.apps.domain_migration_flags.exceptions import DomainMigrationProgressError
from corehq.toggles import DATA_MIGRATION
from corehq.util.quickcache import quickcache
from .models import DomainMigrationProgress, MigrationStatus

log = logging.getLogger(__name__)


def set_migration_started(domain, slug, dry_run=False):
    progress, _ = DomainMigrationProgress.objects.get_or_create(domain=domain, migration_slug=slug)
    if progress.migration_status == MigrationStatus.NOT_STARTED:
        progress.migration_status = MigrationStatus.DRY_RUN if dry_run else MigrationStatus.IN_PROGRESS
        progress.started_on = datetime.utcnow()
        progress.save()
        reset_caches(domain, slug)
    else:
        raise DomainMigrationProgressError(
            'Cannot start a migration that is already in state {}'
            .format(progress.migration_status)
        )


def set_migration_not_started(domain, slug):
    progress, _ = DomainMigrationProgress.objects.get_or_create(domain=domain, migration_slug=slug)
    if migration_in_progress(domain, slug, include_dry_runs=True):
        progress.migration_status = MigrationStatus.NOT_STARTED
        progress.started_on = None
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
        progress.completed_on = datetime.utcnow()
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


def get_uncompleted_migrations(slug):
    """Get a dict of migrations by status that have been started but not completed

    :returns: `{<MigrationStatus>: [<DomainMigrationProgress>, ...], ...}`
    """
    progs = DomainMigrationProgress.objects.filter(
        ~Q(migration_status=MigrationStatus.COMPLETE),
        ~Q(migration_status=MigrationStatus.NOT_STARTED),
        migration_slug=slug,
    )
    result = defaultdict(list)
    for progress in progs:
        if progress.completed_on is not None:
            assert progress.migration_status != MigrationStatus.COMPLETE, progress
            log.warn("uncompleted migation (status=%s) has a completed-on date: %s",
                progress.migration_status, progress.domain)
        result[progress.migration_status].append(progress)
    return result


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
