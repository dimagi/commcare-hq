import random

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from corehq.util.quickcache import quickcache


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
    value = _get_enabled_percent_for_path(campaign, path)
    if 0 < value < 100:
        return random.randint(1, 100) <= value
    return None if value > 100 else (value > 0)


def should_record_metrics(campaign, path):
    """Check if metrics should be recorded for an experiment.

    :return: True if metrics should be recorded, otherwise False.
    """
    return -1 < _get_enabled_percent_for_path(campaign, path) < 102


def get_error_on(campaign, path):
    return {
        96: "old",
        97: "new",
        98: "both",
        99: "diff",
    }.get(_get_enabled_percent_for_path(campaign, path), "none")


def _get_enabled_percent_for_path(campaign, path):
    enablers = _get_enablers(campaign)
    while path and path not in enablers:
        path = path.rsplit(".", 1)[0] if "." in path else ""
    return enablers.get(path, 0)


HALF_HOUR = 30 * 60


@quickcache(
    vary_on=("campaign",),
    timeout=0,  # cache in local memory only
    memoize_timeout=HALF_HOUR,
    session_function=lambda: '',  # share cache across all requests/tasks
)
def _get_enablers(campaign):
    return dict(
        ExperimentEnabler
        .objects.filter(campaign=campaign)
        .values_list("path", "enabled_percent")
    )
