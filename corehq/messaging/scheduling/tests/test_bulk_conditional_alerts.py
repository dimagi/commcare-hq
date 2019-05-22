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
from corehq.messaging.scheduling.forms import ContentForm
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
from corehq.messaging.scheduling.view_helpers import get_conditional_alert_rows, upload_conditional_alert_workbook
from corehq.sql_db.util import run_query_across_partitioned_databases
from corehq.util.workbook_json.excel import get_workbook


class TestBulkConditionalAlerts(TestCase):
    domain = 'bulk-conditional-alert-test'

    EMAIL_RULE = 'email_rule'
    UNTRANSLATED_RULE = 'untranslated_rule'
    DAILY_RULE = 'daily_rule'
    WEEKLY_RULE = 'weekly_rule'

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
        self._rules = {
            self.EMAIL_RULE: self._add_daily_rule(EmailContent(
                subject={'*': 'You just won something'},
                message={'*': 'This is a scam'},
            )),
            self.UNTRANSLATED_RULE: self._add_daily_rule(SMSContent(message={
                '*': 'Joan',
            })),
            self.DAILY_RULE: self._add_daily_rule(SMSContent(message={
                'en': 'Diamonds and Rust',
                'es': 'Diamantes y Óxido',
            })),
            self.WEEKLY_RULE: self._add_weekly_rule(SMSContent(message={
                'en': 'It\'s Too Late',
                'es': 'Es Demasiado Tarde',
            })),
        }

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

    def _get_rule(self, type):
        return AutomaticUpdateRule.objects.get(id=self._rules[type].id)

    def _assertPatternIn(self, pattern, collection):
        self.assertTrue(any(re.match(pattern, item) for item in collection))

    def _add_daily_rule(self, content):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            content
        )
        return self._add_rule(schedule)

    def _add_weekly_rule(self, content):
        schedule = TimedSchedule.create_simple_weekly_schedule(
            self.domain,
            TimedEvent(time=time(12, 0)),
            content,
            [0, 4],
            0,
            total_iterations=3,
            repeat_every=2,
        )
        return self._add_rule(schedule)

    def _add_rule(self, schedule):
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

        self.assertEqual(len(translated_rows), 2)
        self.assertEqual(len(untranslated_rows), 1)

        rows_by_id = {row[0]: row[1:] for row in translated_rows + untranslated_rows}
        self.assertListEqual(rows_by_id[self._get_rule(self.UNTRANSLATED_RULE).id],
                                       ['test', 'person', 'Joan'])
        self.assertListEqual(rows_by_id[self._get_rule(self.DAILY_RULE).id],
                                       ['test', 'person', 'Diamonds and Rust', 'Diamantes y Óxido'])
        self.assertListEqual(rows_by_id[self._get_rule(self.WEEKLY_RULE).id],
                                       ['test', 'person', 'It\'s Too Late', 'Es Demasiado Tarde'])

    def test_upload(self):
        headers = (
            ("translated", ("id", "name", "case_type", "message_en", "message_es")),
            ("not translated", ("id", "name", "case_type", "message")),
        )
        data = (
            ("translated", (
                (self._get_rule(self.DAILY_RULE).id, 'test daily', 'song', 'Rustier', 'Más Oxidado'),
                (self._get_rule(self.UNTRANSLATED_RULE).id, 'test wrong sheet', 'wrong', 'wrong'),
                (self._get_rule(self.EMAIL_RULE).id, 'test email', 'song', 'Email content', 'does not fit'),
                (1000, 'Not a rule', 'person'),
                (self._get_rule(self.WEEKLY_RULE).id, 'test weekly', 'song', 'It\'s On Time', 'Está a Tiempo'),
            )),
            ("not translated", (
                (self._get_rule(self.UNTRANSLATED_RULE).id, 'test untranslated', 'song', 'Joanie'),
                (self._get_rule(self.DAILY_RULE).id, 'test wrong sheet', 'wrong', 'wrong', 'wrong'),
            )),
        )
        file = BytesIO()
        export_raw(headers, data, file, format=Format.XLS_2007)

        with tempfile.TemporaryFile(suffix='.xlsx') as f:
            f.write(file.getvalue())
            f.seek(0)
            workbook = get_workbook(f)
            msgs = [m[1] for m in upload_conditional_alert_workbook(self.domain, self.langs, workbook)]

            self.assertEqual(len(msgs), 6)
            self._assertPatternIn(r"Rule in row 3 with id \d+ does not belong in 'translated' sheet.", msgs)
            self._assertPatternIn(r"Row 4 in 'translated' sheet, with rule id \d+, does not use SMS content", msgs)
            self._assertPatternIn(r"Could not find rule for row 5 in 'translated' sheet, with id \d+", msgs)
            self.assertIn("Updated 2 rule(s) in 'translated' sheet", msgs)
            self._assertPatternIn(r"Rule in row 3 with id \d+ does not belong in 'not translated' sheet.", msgs)
            self.assertIn("Updated 1 rule(s) in 'not translated' sheet", msgs)

            untranslated_rule = self._get_rule(self.UNTRANSLATED_RULE)
            self.assertEqual(untranslated_rule.name, 'test untranslated')
            self.assertEqual(untranslated_rule.case_type, 'song')
            untranslated_content = untranslated_rule.get_messaging_rule_schedule().memoized_events[0].content
            self.assertEqual(untranslated_content.message, {
                '*': 'Joanie',
            })

            # TODO: assert that schedules were preserved
            daily_rule = self._get_rule(self.DAILY_RULE)
            self.assertEqual(daily_rule.name, 'test daily')
            self.assertEqual(daily_rule.case_type, 'song')
            daily_content = daily_rule.get_messaging_rule_schedule().memoized_events[0].content
            self.assertEqual(daily_content.message, {
                'en': 'Rustier',
                'es': 'Más Oxidado',
            })

            weekly_rule = self._get_rule(self.WEEKLY_RULE)
            weekly_content = weekly_rule.get_messaging_rule_schedule().memoized_events[0].content
            self.assertEqual(weekly_content.message, {
                'en': 'It\'s On Time',
                'es': 'Está a Tiempo',
            })
