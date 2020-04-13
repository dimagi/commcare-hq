from functools import partial


def load_counter(load_type, source, domain_name, extra_tags=None):
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

    def track_load(value=1):
        metrics_counter(metric, value, tags=tags)

    return track_load


def case_load_counter(*args, **kw):
    # grep: commcare.load.case
    return load_counter("case", *args, **kw)


def form_load_counter(*args, **kw):
    # grep: commcare.load.form
    return load_counter("form", *args, **kw)


def ledger_load_counter(*args, **kw):
    """Make a ledger transaction load counter function

    Each item counted is a ledger transaction (not a ledger value).
    """
    # grep: commcare.load.ledger
    return load_counter("ledger", *args, **kw)


def sms_load_counter(*args, **kw):
    """Make a messaging load counter function

    This is used to count all kinds of messaging load, including email
    (not strictly SMS).
    """
    # grep: commcare.load.sms
    return load_counter("sms", *args, **kw)


def ucr_load_counter(engine_id, *args, **kw):
    """Make a UCR load counter function

    This is used to count all kinds of UCR load
    """
    # grep: commcare.load.ucr
    return load_counter("ucr.{}".format(engine_id), *args, **kw)


def schedule_load_counter(*args, **kw):
    """Make a schedule load counter function

    This is used to count load from ScheduleInstances
    """
    # grep: commcare.load.schedule
    return load_counter("schedule", *args, **kw)


def load_counter_for_model(model):
    from corehq.form_processor.models import CommCareCaseSQL, XFormInstanceSQL
    from corehq.messaging.scheduling.scheduling_partitioned.models import (
        AlertScheduleInstance, TimedScheduleInstance, CaseTimedScheduleInstance, CaseAlertScheduleInstance
    )
    return {
        CommCareCaseSQL: case_load_counter,
        XFormInstanceSQL: form_load_counter,
        AlertScheduleInstance: schedule_load_counter,
        TimedScheduleInstance: schedule_load_counter,
        CaseTimedScheduleInstance: schedule_load_counter,
        CaseAlertScheduleInstance: schedule_load_counter,
    }.get(model, partial(load_counter, 'unknown'))  # grep: commcare.load.unknown
