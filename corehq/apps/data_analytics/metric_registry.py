import logging
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Literal

from corehq.apps.export.dbaccessors import (
    get_case_exports_by_domain,
    get_form_exports_by_domain,
)

logger = logging.getLogger(__name__)


@dataclass
class MetricDef:
    """Declarative definition of a single domain metric."""
    field_name: str
    cp_name: str
    calc_fn: Callable[['DomainContext'], Any]
    is_boolean: bool = True
    schedule: Literal['daily', 'monthly'] = 'monthly'


class DomainContext:
    """Per-domain context with lazy-cached expensive lookups."""

    def __init__(self, domain_obj, all_stats=None):
        self.domain = domain_obj.name
        self.domain_obj = domain_obj
        self.all_stats = all_stats

    @cached_property
    def apps(self):
        return self.domain_obj.applications()

    @cached_property
    def form_exports(self):
        return get_form_exports_by_domain(self.domain)

    @cached_property
    def case_exports(self):
        return get_case_exports_by_domain(self.domain)


def get_metrics_registry():
    """
    Returns the combined registry of all metrics.

    Used for Salesforce mapping validation.
    """
    from .daily_calcs import DAILY_METRICS
    from .feature_calcs import FEATURE_METRICS

    return DAILY_METRICS + FEATURE_METRICS


def get_metrics_by_schedule(metrics, schedule):
    return [m for m in metrics if m.schedule == schedule]


def collect_metrics_for_domain(domain_obj, metrics, existing_metrics=None):
    """
    Compute metrics for a domain, skipping booleans already True.

    Returns a dict of {field_name: value} for fields that need updating.
    """
    ctx = DomainContext(domain_obj)
    updates = {}
    for metric in metrics:
        if metric.is_boolean and existing_metrics is not None:
            current = getattr(existing_metrics, metric.field_name, None)
            if current is True:
                continue
        try:
            updates[metric.field_name] = metric.calc_fn(ctx)
        except Exception:
            logger.exception(
                "Failed to compute %s for domain %s",
                metric.field_name, domain_obj.name,
            )
    return updates
