from functools import partial
from typing import Any, Callable, Optional, Type

from django.db.models import Model

from .typing import MetricValue, TagValues

LoadCounter = Callable[[MetricValue], None]
LoadCounterGetter = Callable[[str, str, Optional[TagValues]], LoadCounter]


def load_counter(
    load_type: str,
    source: str,
    domain_name: str,
    extra_tags: Optional[TagValues] = None,
) -> LoadCounter:
    """Make a function to track load by counting touched items

    :param load_type: Load type (`"case"`, `"form"`, `"sms"`). Use one
    of the convenience functions below (e.g., `case_load_counter`)
    rather than passing a string literal.
    :param source: Load source string. Example: `"form_submission"`.
    :param domain_name: Domain name string.
    :param extra_tags: Optional dict of extra metric tags.
    :returns: Function that adds load when called: `add_load(value=1)`.
    """
    from corehq.util.metrics import metrics_counter
    tags = extra_tags or {}
    tags['src'] = source
    tags['domain'] = domain_name
    metric = "commcare.load.%s" % load_type

    def track_load(value: MetricValue = 1) -> None:
        metrics_counter(metric, value, tags=tags)

    return track_load


def case_load_counter(
    source: str,
    domain_name: str,
    extra_tags: Optional[TagValues] = None,
) -> LoadCounter:
    # grep: commcare.load.case
    return load_counter("case", source, domain_name, extra_tags)


def form_load_counter(
    source: str,
    domain_name: str,
    extra_tags: Optional[TagValues] = None,
) -> LoadCounter:
    # grep: commcare.load.form
    return load_counter("form", source, domain_name, extra_tags)


def ledger_load_counter(
    source: str,
    domain_name: str,
    extra_tags: Optional[TagValues] = None,
) -> LoadCounter:
    """Make a ledger transaction load counter function

    Each item counted is a ledger transaction (not a ledger value).
    """
    # grep: commcare.load.ledger
    return load_counter("ledger", source, domain_name, extra_tags)


def sms_load_counter(
    source: str,
    domain_name: str,
    extra_tags: Optional[TagValues] = None,
) -> LoadCounter:
    """Make a messaging load counter function

    This is used to count all kinds of messaging load, including email
    (not strictly SMS).
    """
    # grep: commcare.load.sms
    return load_counter("sms", source, domain_name, extra_tags)


def ucr_load_counter(
    engine_id: str,
    source: str,
    domain_name: str,
    extra_tags: Optional[TagValues] = None,
) -> LoadCounter:
    """Make a UCR load counter function

    This is used to count all kinds of UCR load
    """
    # grep: commcare.load.ucr
    return load_counter(f"ucr.{engine_id}", source, domain_name, extra_tags)


def schedule_load_counter(
    source: str,
    domain_name: str,
    extra_tags: Optional[TagValues] = None,
) -> LoadCounter:
    """Make a schedule load counter function

    This is used to count load from ScheduleInstances
    """
    # grep: commcare.load.schedule
    return load_counter("schedule", source, domain_name, extra_tags)


def load_counter_for_model(model: Type[Model]) -> LoadCounterGetter:
    from corehq.form_processor.models import CommCareCase, XFormInstance
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        AlertScheduleInstance,
        CaseAlertScheduleInstance,
        CaseTimedScheduleInstance,
        TimedScheduleInstance,
    )
    return {
        CommCareCase: case_load_counter,
        XFormInstance: form_load_counter,
        AlertScheduleInstance: schedule_load_counter,
        TimedScheduleInstance: schedule_load_counter,
        CaseTimedScheduleInstance: schedule_load_counter,
        CaseAlertScheduleInstance: schedule_load_counter,
    }.get(model, partial(load_counter, 'unknown'))  # grep: commcare.load.unknown
