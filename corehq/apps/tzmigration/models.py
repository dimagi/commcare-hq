from django.db import models


class MigrationStatus(object):
    NOT_STARTED = 'not_started'
    IN_PROGRESS = 'in_progress'
    COMPLETE = 'complete'

    choices = [
        (NOT_STARTED, 'Not Started'),
        (IN_PROGRESS, 'In Progress'),
        (COMPLETE, 'Complete'),
    ]

    max_length = max(len(choice) for choice, _ in choices)


class TimezoneMigrationProgress(models.Model):
    """
    The 2015 timezone migration will happen on a per-domain basis
    This set of "toggles" and associated info
    will be used for the following purposes:
    - to determine how reports, etc. will interpret datetimes
      in form and case data
    - whether to use updated "correct" tz behavior
      or to emulate previous "incorrect" tz behavior when processing forms
    - to track progress of the migration of a domain, during the migration

    """
    domain = models.CharField(max_length=256, null=False, blank=False,
                              db_index=True, primary_key=True)
    migration_status = models.CharField(choices=MigrationStatus.choices,
                                        max_length=MigrationStatus.max_length,
                                        default=MigrationStatus.NOT_STARTED)

    class Meta:
        app_label = 'tzmigration'
