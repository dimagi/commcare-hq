from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import models


class MigrationStatus(object):
    NOT_STARTED = 'not_started'
    IN_PROGRESS = 'in_progress'
    DRY_RUN = 'dry_run'
    COMPLETE = 'complete'

    choices = [
        (NOT_STARTED, 'Not Started'),
        (IN_PROGRESS, 'In Progress'),
        (DRY_RUN, 'Dry Run'),
        (COMPLETE, 'Complete'),
    ]

    max_length = max(len(choice) for choice, _ in choices)


class DomainMigrationProgress(models.Model):
    """
    Flag to track domain migrations
    """
    domain = models.CharField(max_length=256, null=False, default=None)
    migration_slug = models.CharField(max_length=256, null=False, default=None)
    migration_status = models.CharField(choices=MigrationStatus.choices,
                                        max_length=MigrationStatus.max_length,
                                        default=MigrationStatus.NOT_STARTED)
    started_on = models.DateTimeField(null=True, default=None)
    completed_on = models.DateTimeField(null=True, default=None)

    class Meta(object):
        app_label = 'domain_migration_flags'
        unique_together = ('domain', 'migration_slug')
