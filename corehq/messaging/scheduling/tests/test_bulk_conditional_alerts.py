# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db.models import Q
from django.test import TestCase
from datetime import time

from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CreateScheduleInstanceActionDefinition,
)
from corehq.apps.data_interfaces.tests.util import create_empty_rule
from corehq.apps.domain.models import Domain
from corehq.messaging.scheduling.models import (
    TimedEvent,
    TimedSchedule,
    SMSContent,
)
from corehq.apps.users.models import CommCareUser
from corehq.messaging.scheduling.scheduling_partitioned.models import CaseTimedScheduleInstance
from corehq.messaging.scheduling.tests.util import delete_timed_schedules
from corehq.messaging.scheduling.views import get_conditional_alert_rows
from corehq.sql_db.util import run_query_across_partitioned_databases
from corehq.util.test_utils import flag_enabled


class TestBulkConditionalAlerts(TestCase):
    domain = 'bulk-conditional-alert-test'

    @classmethod
    def setUpClass(cls):
        super(TestBulkConditionalAlerts, cls).setUpClass()
        cls.domain_obj = Domain(
            name=cls.domain,
            default_timezone='America/New_York',
        )
        cls.domain_obj.save()
        cls.user = CommCareUser.create(cls.domain, 'test1', 'abc')

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain_obj.delete()
        super(TestBulkConditionalAlerts, cls).tearDownClass()

    def tearDown(self):
        for rule in AutomaticUpdateRule.objects.filter(domain=self.domain):
            rule.hard_delete()

        for instance in run_query_across_partitioned_databases(CaseTimedScheduleInstance, Q(domain=self.domain)):
            delete_case_schedule_instance(instance)

        delete_timed_schedules(self.domain)

    def _add_rule(self, message):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message=message)
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
        self.addCleanup(rule.delete)

        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),)
        )

        rule.save()

        return rule

    def test_download(self):
        translated_rule = self._add_rule({
            'en': 'Diamonds and Rust',
            'es': 'Diamantes y Óxido',
        })
        untranslated_rule = self._add_rule({
            '*': 'Joan',
        })

        rows = get_conditional_alert_rows(self.domain)

        self.assertEqual(len(rows), 2)
        self.assertListEqual(rows[0][1:], ['test', 'person'])
        self.assertListEqual(rows[1][1:], ['test', 'person'])
