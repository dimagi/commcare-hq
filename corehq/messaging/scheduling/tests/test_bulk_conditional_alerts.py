# coding=utf-8
from __future__ import absolute_import
from __future__ import unicode_literals

from django.db.models import Q
from django.test import TestCase
from datetime import time
from io import BytesIO
import re
import tempfile

from couchexport.export import export_raw
from couchexport.models import Format

from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CreateScheduleInstanceActionDefinition,
)
from corehq.apps.data_interfaces.tests.util import create_empty_rule
from corehq.apps.domain.models import Domain
from corehq.messaging.scheduling.models import (
    EmailContent,
    SMSContent,
    TimedEvent,
    TimedSchedule,
)
from corehq.apps.users.models import CommCareUser
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import delete_case_schedule_instance
from corehq.messaging.scheduling.scheduling_partitioned.models import CaseTimedScheduleInstance
from corehq.messaging.scheduling.tests.util import delete_timed_schedules
from corehq.messaging.scheduling.views import get_conditional_alert_rows, upload_conditional_alert_rows
from corehq.sql_db.util import run_query_across_partitioned_databases
from corehq.util.workbook_json.excel import get_workbook


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
        cls.langs = ['en', 'es']

    def setUp(self):
        self._translated_rule = self._add_rule(SMSContent(message={
            'en': 'Diamonds and Rust',
            'es': 'Diamantes y Óxido',
        }))
        self._untranslated_rule = self._add_rule(SMSContent(message={
            '*': 'Joan',
        }))
        self._email_rule = self._add_rule(EmailContent(
            subject={'*': 'You just won something'},
            message={'*': 'This is a scam'},
        ))

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

    @property
    def translated_rule(self):
        return AutomaticUpdateRule.objects.get(id=self._translated_rule.id)

    @property
    def untranslated_rule(self):
        return AutomaticUpdateRule.objects.get(id=self._untranslated_rule.id)

    @property
    def email_rule(self):
        return AutomaticUpdateRule.objects.get(id=self._email_rule.id)

    def _assertPatternIn(self, pattern, collection):
        self.assertTrue(any(re.match(pattern, item) for item in collection))

    def _add_rule(self, content):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            content
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
        (translated_rows, untranslated_rows) = get_conditional_alert_rows(self.domain, self.langs)

        self.assertEqual(len(translated_rows), 1)
        self.assertListEqual(translated_rows[0][1:], ['test', 'person', 'Diamonds and Rust', 'Diamantes y Óxido'])

        self.assertEqual(len(untranslated_rows), 1)
        self.assertListEqual(untranslated_rows[0][1:], ['test', 'person', 'Joan'])

    def test_upload(self):
        headers = (("translations", ("id", "name", "case_type")),)
        data = (
            ("translations", (
                (self.translated_rule.id, 'test updated', 'song'),
                (self.email_rule.id, 'test email', 'song'),
                (1000, 'Not a rule', 'person'),
            )),
        )
        file = BytesIO()
        export_raw(headers, data, file, format=Format.XLS_2007)

        with tempfile.TemporaryFile(suffix='.xlsx') as f:
            f.write(file.getvalue())
            f.seek(0)
            workbook = get_workbook(f)
            msgs = [m[1] for m in upload_conditional_alert_rows(self.domain, workbook.get_worksheet())]
            self.assertEqual(len(msgs), 3)
            self._assertPatternIn(r"Row 3, with rule id \d+, does not use SMS content", msgs)
            self._assertPatternIn(r"Could not find rule for row 4, with id \d+", msgs)
            self.assertIn("Updated 1 rule(s)", msgs)
            self.assertEqual(self.translated_rule.name, 'test updated')
            self.assertEqual(self.translated_rule.case_type, 'song')
            self.assertEqual(self.untranslated_rule.name, 'test')
            self.assertEqual(self.untranslated_rule.case_type, 'person')
