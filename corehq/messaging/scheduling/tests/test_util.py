from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.data_interfaces.tests.util import create_empty_rule
from corehq.messaging.scheduling.models import (
    ScheduledBroadcast,
    ImmediateBroadcast,
    TimedSchedule,
    AlertSchedule,
)
from corehq.messaging.scheduling.util import domain_has_reminders
from datetime import date
from django.test import TestCase


class TestMessagingModelLookups(TestCase):

    domain = 'messaging-lookup-test'

    def test_domain_has_conditional_alerts(self):
        self.assertFalse(AutomaticUpdateRule.domain_has_conditional_alerts(self.domain))
        self.assertFalse(domain_has_reminders(self.domain))

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
        self.addCleanup(rule.delete)

        self.assertTrue(AutomaticUpdateRule.domain_has_conditional_alerts(self.domain))
        self.assertTrue(domain_has_reminders(self.domain))

    def test_domain_has_scheduled_broadcasts(self):
        self.assertFalse(ScheduledBroadcast.domain_has_broadcasts(self.domain))
        self.assertFalse(domain_has_reminders(self.domain))

        schedule = TimedSchedule.objects.create(domain=self.domain, repeat_every=1, total_iterations=1)
        self.addCleanup(schedule.delete)

        broadcast = ScheduledBroadcast.objects.create(domain=self.domain, name='', schedule=schedule,
            start_date=date(2018, 7, 1))
        self.addCleanup(broadcast.delete)

        self.assertTrue(ScheduledBroadcast.domain_has_broadcasts(self.domain))
        self.assertTrue(domain_has_reminders(self.domain))

    def test_domain_has_immediate_broadcasts(self):
        self.assertFalse(ImmediateBroadcast.domain_has_broadcasts(self.domain))
        self.assertFalse(domain_has_reminders(self.domain))

        schedule = AlertSchedule.objects.create(domain=self.domain)
        self.addCleanup(schedule.delete)

        broadcast = ImmediateBroadcast.objects.create(domain=self.domain, name='', schedule=schedule)
        self.addCleanup(broadcast.delete)

        self.assertTrue(ImmediateBroadcast.domain_has_broadcasts(self.domain))
        self.assertTrue(domain_has_reminders(self.domain))
