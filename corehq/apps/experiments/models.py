from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ExperimentEnabler(models.Model):
    campaign = models.CharField(
        max_length=255,
        help_text="Identifier for a group of related experiments.",
    )
    path = models.CharField(
        blank=True,
        max_length=1024,
        help_text="Example: corehq.apps.experiments.func Partial paths "
                  "may be specified to match all experiments in a namespace. "
                  "An empty string matches all experiments.",
    )
    enabled_percent = models.SmallIntegerField(
        default=0,
        validators=[MinValueValidator(-1), MaxValueValidator(102)],
        help_text="Zero means run only old, -1 to disable metrics as well. "
                  "1-100 means % of time to run new. 101 means run only "
                  "new, 102 to disable metrics as well.",
    )

    class Meta:
        app_label = "experiments"
        unique_together = ("campaign", "path")


def is_enabled(campaign, path):
    """Check which code path should be run.

    :return: False if only the old code path should run, True if both
        old and new should run, and None if only new should run.
    """
    value = (
        ExperimentEnabler.objects
        .filter(campaign=campaign, path=path)
        .values("enabled_percent").first()
    ).get("enabled_percent", -1)
    return None if value > 100 else (value > 0)


def should_record_metrics(campaign, path):
    """Check if metrics should be recorded for an experiment.

    :return: True if metrics should be recorded, otherwise False.
    """
    value = (
        ExperimentEnabler.objects
        .filter(campaign=campaign, path=path)
        .values("enabled_percent").first()
    ).get("enabled_percent", -1)
    return -1 < value < 102
