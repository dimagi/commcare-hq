from datetime import datetime


def utcnow():
    """
    Defined here to do patching in tests.
    """
    return datetime.utcnow()


def domain_has_reminders(domain):
    from corehq.apps.data_interfaces.models import AutomaticUpdateRule
    from corehq.messaging.scheduling.models import ScheduledBroadcast, ImmediateBroadcast

    return (
        AutomaticUpdateRule.domain_has_conditional_alerts(domain) or
        ScheduledBroadcast.domain_has_broadcasts(domain) or
        ImmediateBroadcast.domain_has_broadcasts(domain)
    )
