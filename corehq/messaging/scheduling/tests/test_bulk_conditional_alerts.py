from collections import defaultdict
from django.db.models import Q
from django.test import TestCase
from datetime import time
from io import BytesIO
from unittest.mock import patch
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
    AlertEvent,
    AlertSchedule,
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
from corehq.sql_db.util import paginate_query_across_partitioned_databases
from corehq.util.workbook_json.excel import get_workbook


class TestBulkConditionalAlerts(TestCase):
    domain = 'bulk-conditional-alert-test'

    EMAIL_RULE = 'email_rule'
    LOCKED_RULE = 'locked_rule'
    UNTRANSLATED_IMMEDIATE_RULE = 'untranslated_immediate_rule'
    UNTRANSLATED_DAILY_RULE = 'untranslated_daily_rule'
    IMMEDIATE_RULE = 'immediate_rule'
    DAILY_RULE = 'daily_rule'
    WEEKLY_RULE = 'weekly_rule'
    MONTHLY_RULE = 'monthly_rule'
    CUSTOM_IMMEDIATE_RULE = 'custom_immediate_rule'
    CUSTOM_RULE_BOTH_SHEETS = 'custom_immediate_rule_both_sheets'
    CUSTOM_DAILY_RULE = 'custom_daily_rule'

    @classmethod
    def setUpClass(cls):
        super(TestBulkConditionalAlerts, cls).setUpClass()
        cls.domain_obj = Domain(
            name=cls.domain,
            default_timezone='America/New_York',
        )
        cls.domain_obj.save()
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.user = CommCareUser.create(cls.domain, 'test1', 'abc', None, None)
        cls.addClassCleanup(cls.user.delete, cls.domain, deleted_by=None)
        cls.langs = ['en', 'es']

    def setUp(self):
        self._rules = {
            self.EMAIL_RULE: self._add_daily_rule(EmailContent(
                subject={'*': 'You just won something'},
                message={'*': 'This is a scam'},
            )),
            self.LOCKED_RULE: self._add_immediate_rule(SMSContent(message={
                '*': 'Fool That I Am',
            })),
            self.UNTRANSLATED_IMMEDIATE_RULE: self._add_immediate_rule(SMSContent(message={
                '*': 'Joni',
            })),
            self.UNTRANSLATED_DAILY_RULE: self._add_daily_rule(SMSContent(message={
                '*': 'Joan',
            })),
            self.IMMEDIATE_RULE: self._add_immediate_rule(SMSContent(message={
                '*': 'Car on a Hill',
            })),
            self.DAILY_RULE: self._add_daily_rule(SMSContent(message={
                'en': 'Diamonds and Rust',
                'es': 'Diamantes y Óxido',
            })),
            self.WEEKLY_RULE: self._add_weekly_rule(SMSContent(message={
                'en': 'It\'s Too Late',
                'es': 'Es Demasiado Tarde',
            })),
            self.MONTHLY_RULE: self._add_monthly_rule(SMSContent(message={
                'en': 'Both Sides Now',
                'es': 'Ahora Ambos Lados',
            })),
            self.CUSTOM_DAILY_RULE: self._add_custom_daily_rule([
                SMSContent(message={'*': 'Just Like This Train'}),
                SMSContent(message={'*': 'Free Man in Paris'}),
            ]),
            self.CUSTOM_IMMEDIATE_RULE: self._add_custom_immediate_rule([
                SMSContent(message={
                    'en': 'Paper Bag',
                    'es': 'Bolsa de Papel',
                }),
                SMSContent(message={
                    'en': 'A Mistake',
                    'es': 'Un Error',
                }),
            ]),
            self.CUSTOM_RULE_BOTH_SHEETS: self._add_custom_immediate_rule([
                SMSContent(message={
                    'en': "I'm Lucky",
                    'es': "Tengo Suerte",
                }),
                SMSContent(message={
                    '*': 'Down to Zero',
                }),
                SMSContent(message={
                    'en': 'Me Myself I',
                    'es': 'Yo Mí Mismo Yo',
                }),
                SMSContent(message={
                    '*': 'Rosie',
                }),
            ])
        }
        locked_rule = self._get_rule(self.LOCKED_RULE)
        locked_rule.locked_for_editing = True
        locked_rule.save()

    def tearDown(self):
        for rule in AutomaticUpdateRule.objects.filter(domain=self.domain):
            rule.hard_delete()

        for instance in paginate_query_across_partitioned_databases(
                CaseTimedScheduleInstance, Q(domain=self.domain)):
            delete_case_schedule_instance(instance)

        delete_timed_schedules(self.domain)

    def _get_rule(self, type):
        return AutomaticUpdateRule.objects.get(id=self._rules[type].id)

    def _assertPatternIn(self, pattern, collection):
        self.assertTrue(any(re.match(pattern, item) for item in collection))

    def _assertAlertScheduleEventsEqual(self, schedule1, schedule2):
        self.assertEqual(len(schedule1.memoized_events), len(schedule2.memoized_events))
        for i in range(len(schedule1.memoized_events)):
            event1 = schedule1.memoized_events[i]
            event2 = schedule2.memoized_events[i]
            self.assertTrue(isinstance(event1, AlertEvent))
            self.assertTrue(isinstance(event2, AlertEvent))
            self.assertEqual(event1.minutes_to_wait, event2.minutes_to_wait)

    def _assertTimedScheduleEventsEqual(self, schedule1, schedule2):
        self.assertEqual(len(schedule1.memoized_events), len(schedule2.memoized_events))
        for i in range(len(schedule1.memoized_events)):
            event1 = schedule1.memoized_events[i]
            event2 = schedule2.memoized_events[i]
            self.assertTrue(isinstance(event1, TimedEvent))
            self.assertTrue(isinstance(event2, TimedEvent))
            self.assertEqual(event1.day, event2.day)
            self.assertEqual(event1.get_scheduling_info(), event2.get_scheduling_info())

    def _assertContent(self, schedule, message):
        for event in schedule.memoized_events:
            self.assertEqual(event.content.message, message)

    def _assertCustomContent(self, schedule, messages):
        events = schedule.memoized_events
        self.assertEqual(len(messages), len(events))
        for i, event in enumerate(events):
            self.assertEqual(messages[i], events[i].content.message)

    def _add_immediate_rule(self, content):
        schedule = AlertSchedule.create_simple_alert(self.domain, content)
        return self._add_rule(alert_schedule_id=schedule.schedule_id)

    def _add_daily_rule(self, content):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            content
        )
        return self._add_rule(timed_schedule_id=schedule.schedule_id)

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
        return self._add_rule(timed_schedule_id=schedule.schedule_id)

    def _add_monthly_rule(self, content):
        schedule = TimedSchedule.create_simple_monthly_schedule(
            self.domain,
            TimedEvent(time=time(11, 0)),
            [23, -1],
            content,
            total_iterations=2,
        )
        return self._add_rule(timed_schedule_id=schedule.schedule_id)

    def _add_custom_immediate_rule(self, content_list):
        event_and_content_objects = [
            (AlertEvent(minutes_to_wait=i * 10), content)
            for i, content in enumerate(content_list)
        ]
        schedule = AlertSchedule.create_custom_alert(self.domain, event_and_content_objects)
        return self._add_rule(alert_schedule_id=schedule.schedule_id)

    def _add_custom_daily_rule(self, content_list):
        event_and_content_objects = [
            (TimedEvent(day=i % 7, time=time(i * 2 % 24, 30 + i % 60)), content)
            for i, content in enumerate(content_list)
        ]
        schedule = TimedSchedule.create_custom_daily_schedule(
            self.domain,
            event_and_content_objects,
            repeat_every=2,
        )
        return self._add_rule(timed_schedule_id=schedule.schedule_id)

    def _add_rule(self, alert_schedule_id=None, timed_schedule_id=None):
        assert alert_schedule_id or timed_schedule_id
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
        self.addCleanup(rule.delete)
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            recipients=(('CommCareUser', self.user.get_id),),
            alert_schedule_id=alert_schedule_id,
            timed_schedule_id=timed_schedule_id,
        )
        rule.save()
        return rule

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_download(self, language_list_patch):
        language_list_patch.return_value = self.langs
        (translated_rows, untranslated_rows) = get_conditional_alert_rows(self.domain)

        self.assertEqual(len(translated_rows), 7)
        self.assertEqual(len(untranslated_rows), 8)

        rows_by_id = defaultdict(list)
        for row in translated_rows + untranslated_rows:
            rows_by_id[row[0]].append(row[1:])

        self.assertListEqual(rows_by_id[self._get_rule(self.UNTRANSLATED_IMMEDIATE_RULE).id],
                                       [['test', 'Joni']])
        self.assertListEqual(rows_by_id[self._get_rule(self.UNTRANSLATED_DAILY_RULE).id],
                                       [['test', 'Joan']])
        self.assertListEqual(rows_by_id[self._get_rule(self.IMMEDIATE_RULE).id],
                                       [['test', 'Car on a Hill']])
        self.assertListEqual(rows_by_id[self._get_rule(self.CUSTOM_IMMEDIATE_RULE).id],
                                       [['test', 'Paper Bag', 'Bolsa de Papel'],
                                        ['test', 'A Mistake', 'Un Error']])

        self.assertListEqual(rows_by_id[self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id],
                                       [['test', "I'm Lucky", "Tengo Suerte"],
                                        ['test', 'Me Myself I', 'Yo Mí Mismo Yo'],
                                        ['test', 'Down to Zero'],
                                        ['test', 'Rosie']])

        self.assertListEqual(rows_by_id[self._get_rule(self.DAILY_RULE).id],
                                       [['test', 'Diamonds and Rust', 'Diamantes y Óxido']])
        self.assertListEqual(rows_by_id[self._get_rule(self.WEEKLY_RULE).id],
                                       [['test', 'It\'s Too Late', 'Es Demasiado Tarde']])
        self.assertListEqual(rows_by_id[self._get_rule(self.MONTHLY_RULE).id],
                                       [['test', 'Both Sides Now', 'Ahora Ambos Lados']])
        self.assertListEqual(rows_by_id[self._get_rule(self.LOCKED_RULE).id],
                                       [['test', 'Fool That I Am']])
        self.assertListEqual(rows_by_id[self._get_rule(self.CUSTOM_DAILY_RULE).id],
                                       [['test', 'Just Like This Train'],
                                        ['test', 'Free Man in Paris']])

    def _upload(self, data, headers=None):
        if headers is None:
            headers = (
                ("translated", ("id", "name", "message_en", "message_es")),
                ("not translated", ("id", "name", "message")),
            )

        file = BytesIO()
        export_raw(headers, data, file, format=Format.XLS_2007)

        with tempfile.TemporaryFile(suffix='.xlsx') as f:
            f.write(file.getvalue())
            f.seek(0)
            workbook = get_workbook(f)
            msgs = upload_conditional_alert_workbook(self.domain, workbook)
            return [m[1] for m in msgs]     # msgs is tuples of (type, message); ignore the type

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_upload(self, language_list_patch):
        language_list_patch.return_value = self.langs
        data = (
            ("translated", (
                (self._get_rule(self.DAILY_RULE).id, 'test daily', 'Rustier', 'Más Oxidado'),
                (self._get_rule(self.UNTRANSLATED_DAILY_RULE).id, 'test change sheet', 'Joanie', 'Juana'),
                (self._get_rule(self.EMAIL_RULE).id, 'test email', 'Email content', 'does not fit'),
                (1000, 'Not a rule'),
                (self._get_rule(self.WEEKLY_RULE).id, 'test weekly', 'It\'s On Time', 'Está a Tiempo'),
            )),
            ("not translated", (
                (self._get_rule(self.UNTRANSLATED_IMMEDIATE_RULE).id, 'test untranslated', 'Roberta'),
                (self._get_rule(self.IMMEDIATE_RULE).id, 'test immediate', 'Bicycle on a Hill'),
                (self._get_rule(self.LOCKED_RULE).id, 'test locked', 'nope'),
                (None, 'missing id', 'is bad'),
                (self._get_rule(self.MONTHLY_RULE).id, 'test monthly change sheet', 'The Other Side Now'),
            )),
        )

        test_cases = (self.UNTRANSLATED_IMMEDIATE_RULE, self.UNTRANSLATED_DAILY_RULE, self.IMMEDIATE_RULE,
                      self.DAILY_RULE, self.WEEKLY_RULE, self.MONTHLY_RULE)
        old_schedules = {test_case: self._get_rule(test_case).get_schedule()
                         for test_case in test_cases}

        msgs = self._upload(data)

        self.assertEqual(len(msgs), 6)
        self._assertPatternIn(r"Row 4 in 'translated' sheet, with rule id \d+, does not use SMS content", msgs)
        self._assertPatternIn(r"Could not find rule for row 5 in 'translated' sheet, with id \d+", msgs)
        self.assertIn("Updated 3 rule(s) in 'translated' sheet", msgs)
        self._assertPatternIn(r"Row 4 in 'not translated' sheet.* rule id \d+, .*currently processing", msgs)
        self.assertIn(r"Row 5 in 'not translated' sheet is missing an id.", msgs)

        untranslated_immediate_rule = self._get_rule(self.UNTRANSLATED_IMMEDIATE_RULE)
        self.assertEqual(untranslated_immediate_rule.name, 'test untranslated')
        self.assertEqual(untranslated_immediate_rule.case_type, 'person')
        untranslated_schedule = untranslated_immediate_rule.get_schedule()
        self._assertAlertScheduleEventsEqual(untranslated_schedule,
                                             old_schedules[self.UNTRANSLATED_IMMEDIATE_RULE])
        untranslated_content = untranslated_schedule.memoized_events[0].content
        self.assertEqual(untranslated_content.message, {
            '*': 'Roberta',
        })

        untranslated_daily_rule = self._get_rule(self.UNTRANSLATED_DAILY_RULE)
        self.assertEqual(untranslated_daily_rule.name, 'test change sheet')
        self.assertEqual(untranslated_daily_rule.case_type, 'person')
        untranslated_schedule = untranslated_daily_rule.get_schedule()
        self._assertTimedScheduleEventsEqual(untranslated_schedule, old_schedules[self.UNTRANSLATED_DAILY_RULE])
        untranslated_content = untranslated_schedule.memoized_events[0].content
        self.assertEqual(untranslated_content.message, {
            'en': 'Joanie',
            'es': 'Juana',
        })

        immediate_rule = self._get_rule(self.IMMEDIATE_RULE)
        self.assertEqual(immediate_rule.name, 'test immediate')
        immediate_schedule = immediate_rule.get_schedule()
        self._assertAlertScheduleEventsEqual(immediate_schedule, old_schedules[self.IMMEDIATE_RULE])
        immediate_content = immediate_schedule.memoized_events[0].content
        self.assertEqual(immediate_content.message, {
            '*': 'Bicycle on a Hill',
        })

        daily_rule = self._get_rule(self.DAILY_RULE)
        self.assertEqual(daily_rule.name, 'test daily')
        daily_schedule = daily_rule.get_schedule()
        self._assertTimedScheduleEventsEqual(daily_schedule, old_schedules[self.DAILY_RULE])
        self._assertContent(daily_schedule, {
            'en': 'Rustier',
            'es': 'Más Oxidado',
        })

        weekly_rule = self._get_rule(self.WEEKLY_RULE)
        weekly_schedule = weekly_rule.get_schedule()
        self._assertTimedScheduleEventsEqual(weekly_schedule, old_schedules[self.WEEKLY_RULE])
        self._assertContent(weekly_schedule, {
            'en': 'It\'s On Time',
            'es': 'Está a Tiempo',
        })

        monthly_rule = self._get_rule(self.MONTHLY_RULE)
        monthly_schedule = monthly_rule.get_schedule()
        self._assertTimedScheduleEventsEqual(monthly_schedule, old_schedules[self.MONTHLY_RULE])
        self._assertContent(monthly_schedule, {
            '*': 'The Other Side Now',
        })

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_upload_custom_schedule(self, language_list_patch):
        language_list_patch.return_value = self.langs
        data = (
            ("translated", (
                (self._get_rule(self.CUSTOM_IMMEDIATE_RULE).id, 'test', 'Plastic Bag', 'Bolsa de Plastico'),
                (self._get_rule(self.CUSTOM_IMMEDIATE_RULE).id, 'test', 'A Correction', 'Una Corrección'),
            )),
            ("not translated", (
                (self._get_rule(self.CUSTOM_DAILY_RULE).id, 'test', 'Not Like This Train'),
                (self._get_rule(self.CUSTOM_DAILY_RULE).id, 'test', 'Free Man in Nice'),
            )),
        )

        test_cases = (self.CUSTOM_IMMEDIATE_RULE, self.CUSTOM_DAILY_RULE)
        old_schedules = {test_case: self._get_rule(test_case).get_schedule()
                         for test_case in test_cases}

        msgs = self._upload(data)

        self.assertEqual(len(msgs), 2)
        self.assertIn("Updated 1 rule(s) in 'translated' sheet", msgs)
        self.assertIn("Updated 1 rule(s) in 'not translated' sheet", msgs)

        custom_daily_rule = self._get_rule(self.CUSTOM_DAILY_RULE)
        custom_daily_schedule = custom_daily_rule.get_schedule()
        self._assertTimedScheduleEventsEqual(custom_daily_schedule, old_schedules[self.CUSTOM_DAILY_RULE])
        self._assertCustomContent(custom_daily_schedule, [
            {'*': 'Not Like This Train'},
            {'*': 'Free Man in Nice'},
        ])

        custom_immediate_rule = self._get_rule(self.CUSTOM_IMMEDIATE_RULE)
        custom_immediate_schedule = custom_immediate_rule.get_schedule()
        self._assertAlertScheduleEventsEqual(custom_immediate_schedule, old_schedules[self.CUSTOM_IMMEDIATE_RULE])
        self._assertCustomContent(custom_immediate_schedule, [{
            'en': 'Plastic Bag',
            'es': 'Bolsa de Plastico',
        }, {
            'en': 'A Correction',
            'es': 'Una Corrección',
        }])

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_upload_custom_schedule_both_sheets(self, language_list_patch):
        """
        This tests a rule that has a custom schedule with a mix of translated and untranslated messages.
        """
        language_list_patch.return_value = self.langs
        data = (
            ("translated", (
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', "You're Lucky", "Tienes Suerte"),
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', "You Yourself You", "Tú Tú Mismo Tú"),
            )),
            ("not translated", (
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', 'Down to One'),
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', 'Willow'),
            )),
        )

        old_schedule = self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).get_schedule()

        msgs = self._upload(data)
        self.assertEqual(len(msgs), 2)
        self.assertIn("Updated 1 rule(s) in 'translated' sheet", msgs)
        self.assertIn("Updated 1 rule(s) in 'not translated' sheet", msgs)

        rule = self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS)
        schedule = rule.get_schedule()
        self._assertAlertScheduleEventsEqual(schedule, old_schedule)
        self._assertCustomContent(schedule, [{
            'en': "You're Lucky",
            'es': "Tienes Suerte",
        }, {
            '*': 'Down to One',
        }, {
            'en': "You Yourself You",
            'es': "Tú Tú Mismo Tú",
        }, {
            '*': 'Willow',
        }])

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_upload_custom_schedule_both_sheets_swap(self, language_list_patch):
        language_list_patch.return_value = self.langs
        # This rule originally has two translated messages and two untranslated.
        # Trying to move just one of the messages to the other sheet should fail.
        data = (
            ("translated", (
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', "You're Lucky", "Tienes Suerte"),
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', "You Yourself You", "Tú Tú Mismo Tú"),
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', 'Down to One', 'Solamente Uno'),
            )),
            ("not translated", (
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', 'Willow'),
            )),
        )

        msgs = self._upload(data)

        self.assertEqual(len(msgs), 4)
        self.assertIn("Updated 0 rule(s) in 'translated' sheet", msgs)
        self.assertIn("Updated 0 rule(s) in 'not translated' sheet", msgs)
        self._assertPatternIn(r"Could not update rule with id \d+ in 'translated' sheet: "
                              r"expected 2 .* but found 3.", msgs)
        self._assertPatternIn(r"Could not update rule with id \d+ in 'not translated' sheet: "
                              r"expected 2 .* but found 1.", msgs)

        # Moving all of the messages to the same sheet should work.
        data = (
            ("translated", (
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', "You're Lucky", "Tienes Suerte"),
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', 'Down to One', 'Solamente Uno'),
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', "You Yourself You", "Tú Tú Mismo Tú"),
                (self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).id, 'test', 'Willow', 'Árbol'),
            )),
            ("not translated", ()),
        )

        old_schedule = self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS).get_schedule()
        msgs = self._upload(data)

        self.assertEqual(len(msgs), 2)
        self.assertIn("Updated 1 rule(s) in 'translated' sheet", msgs)
        self.assertIn("Updated 0 rule(s) in 'not translated' sheet", msgs)

        rule = self._get_rule(self.CUSTOM_RULE_BOTH_SHEETS)
        schedule = rule.get_schedule()
        self._assertAlertScheduleEventsEqual(schedule, old_schedule)
        self._assertCustomContent(schedule, [{
            'en': "You're Lucky",
            'es': "Tienes Suerte",
        }, {
            'en': 'Down to One',
            'es': 'Solamente Uno'
        }, {
            'en': "You Yourself You",
            'es': "Tú Tú Mismo Tú",
        }, {
            'en': 'Willow',
            'es': 'Árbol',
        }])

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_upload_custom_schedule_message_count_mismatch(self, language_list_patch):
        language_list_patch.return_value = self.langs

        data = (
            ("translated", (
                (self._get_rule(self.CUSTOM_IMMEDIATE_RULE).id, 'test', 'Plastic Bag', 'Bolsa de Plastico'),
                (self._get_rule(self.CUSTOM_IMMEDIATE_RULE).id, 'test', 'Cloth Bag', 'Bolsa de Tela'),
                (self._get_rule(self.CUSTOM_IMMEDIATE_RULE).id, 'test', 'Fishnet Bag', 'Bolsa de Red'),
            )),
            ("not translated", (
                (self._get_rule(self.CUSTOM_DAILY_RULE).id, 'test', 'Like That Other Train'),
            )),
        )

        msgs = self._upload(data)

        self.assertEqual(len(msgs), 4)
        self.assertIn("Updated 0 rule(s) in 'translated' sheet", msgs)
        self.assertIn("Updated 0 rule(s) in 'not translated' sheet", msgs)
        self._assertPatternIn(r"Could not update rule with id \d+ in 'translated' sheet: "
                              r"expected 2 .* but found 3.", msgs)
        self._assertPatternIn(r"Could not update rule with id \d+ in 'not translated' sheet: "
                              r"expected 2 .* but found 1.", msgs)

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_upload_custom_schedule_name_mismatch(self, language_list_patch):
        language_list_patch.return_value = self.langs

        data = (
            ("translated", ()),
            ("not translated", (
                (self._get_rule(self.CUSTOM_DAILY_RULE).id, 'test', 'Like That Other Train'),
                (self._get_rule(self.CUSTOM_DAILY_RULE).id, 'test different name', 'Free Man in Nice'),
            )),
        )

        msgs = self._upload(data)

        self.assertEqual(len(msgs), 3)
        self.assertIn("Updated 0 rule(s) in 'translated' sheet", msgs)
        self.assertIn("Updated 0 rule(s) in 'not translated' sheet", msgs)
        self._assertPatternIn(r"Error updating rule with id \d+ in 'not translated' sheet: "
                              r"Rule name must be the same", msgs)

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_upload_blank_content(self, language_list_patch):
        language_list_patch.return_value = self.langs
        headers = (
            ("translated", ("id", "name", "message_en", "message_es")),
            ("not translated", ("id", "name", "message")),
        )
        data = (
            ("translated", (
                (self._get_rule(self.DAILY_RULE).id, 'test daily', '', 'Más Oxidado'),
                (self._get_rule(self.MONTHLY_RULE).id, 'test monthly', 'The Far Side', ''),
            )),
            ("not translated", (
                (self._get_rule(self.UNTRANSLATED_IMMEDIATE_RULE).id, 'test untranslated', 'Cannot be blank'),
            )),
        )

        msgs = self._upload(data, headers)

        self.assertEqual(len(msgs), 2)
        self.assertIn("Updated 2 rule(s) in 'translated' sheet", msgs)
        daily_rule = self._get_rule(self.DAILY_RULE)
        daily_content = daily_rule.get_schedule().memoized_events[0].content
        self.assertEqual(daily_content.message, {
            'en': '',
            'es': 'Más Oxidado',
        })
        monthly_rule = self._get_rule(self.MONTHLY_RULE)
        monthly_content = monthly_rule.get_schedule().memoized_events[0].content
        self.assertEqual(monthly_content.message, {
            'en': 'The Far Side',
            'es': '',
        })
        self.assertIn("Updated 1 rule(s) in 'not translated' sheet", msgs)
        untranslated_rule = self._get_rule(self.UNTRANSLATED_IMMEDIATE_RULE)
        untranslated_content = untranslated_rule.get_schedule().memoized_events[0].content
        self.assertEqual(untranslated_content.message, {
            '*': 'Cannot be blank',
        })

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_partial_upload(self, language_list_patch):
        language_list_patch.return_value = self.langs
        headers = (
            ("translated", ("id", "name", "message_es")),
            ("not translated", ("id", "name")),
        )
        data = (
            ("translated", (
                (self._get_rule(self.DAILY_RULE).id, 'test daily', 'Más Oxidado'),
            )),
            ("not translated", (
                (self._get_rule(self.UNTRANSLATED_DAILY_RULE).id, 'test untranslated'),
            )),
        )

        msgs = self._upload(data, headers)

        self.assertEqual(len(msgs), 2)
        self.assertIn("Updated 1 rule(s) in 'translated' sheet", msgs)
        self.assertIn("Updated 1 rule(s) in 'not translated' sheet", msgs)

        untranslated_rule = self._get_rule(self.UNTRANSLATED_DAILY_RULE)
        self.assertEqual(untranslated_rule.name, 'test untranslated')
        self.assertEqual(untranslated_rule.case_type, 'person')
        untranslated_content = untranslated_rule.get_schedule().memoized_events[0].content
        self.assertEqual(untranslated_content.message, {
            '*': 'Joan',
        })

        daily_rule = self._get_rule(self.DAILY_RULE)
        self.assertEqual(daily_rule.name, 'test daily')
        self.assertEqual(daily_rule.case_type, 'person')
        daily_content = daily_rule.get_schedule().memoized_events[0].content
        self.assertEqual(daily_content.message, {
            'en': 'Diamonds and Rust',
            'es': 'Más Oxidado',
        })

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_upload_missing_id_column(self, language_list_patch):
        language_list_patch.return_value = self.langs
        headers = (
            ("translated", ("name", "message_en", "message_es")),
            ("not translated", ("id", "name", "message")),
        )
        data = (
            ("translated", (
                ('test daily', 'Rustier', 'Más Oxidado'),
            )),
            ("not translated", (
                (self._get_rule(self.UNTRANSLATED_DAILY_RULE).id, 'test untranslated', 'Joanie'),
            )),
        )

        msgs = self._upload(data, headers)

        self.assertEqual(len(msgs), 2)
        self.assertIn("The 'translated' sheet is missing an id column. This sheet has been skipped.", msgs)
        self.assertIn("Updated 1 rule(s) in 'not translated' sheet", msgs)

        untranslated_rule = self._get_rule(self.UNTRANSLATED_DAILY_RULE)
        self.assertEqual(untranslated_rule.name, 'test untranslated')
        untranslated_content = untranslated_rule.get_schedule().memoized_events[0].content
        self.assertEqual(untranslated_content.message, {
            '*': 'Joanie',
        })

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_upload_blank_translated_message_should_fail(self, language_list_patch):
        language_list_patch.return_value = self.langs
        headers = (
            ("translated", ("id", "name", "message_en", "message_es")),
            ("not translated", ("id", "name")),
        )
        data = (
            ("translated", (
                (self._get_rule(self.DAILY_RULE).id, 'test', '', ''),
            )),
            ("not translated", (
                (self._get_rule(self.UNTRANSLATED_DAILY_RULE).id, 'test'),
            )),
        )

        msgs = self._upload(data, headers)

        daily_rule = self._get_rule(self.DAILY_RULE)
        self.assertEqual(msgs, [
            f"Error updating rule with id {daily_rule.id} in 'translated' sheet: Missing message",
            "Updated 0 rule(s) in 'translated' sheet",
            "Updated 0 rule(s) in 'not translated' sheet",
        ])
        daily_content = daily_rule.get_schedule().memoized_events[0].content
        self.assertEqual(daily_content.message, {
            'en': 'Diamonds and Rust',
            'es': 'Diamantes y Óxido',
        })

    @patch('corehq.messaging.scheduling.view_helpers.get_language_list')
    def test_upload_blank_untranslated_message_should_fail(self, language_list_patch):
        language_list_patch.return_value = self.langs
        headers = (
            ("translated", ("id", "name")),
            ("not translated", ("id", "name", "message")),
        )
        data = (
            ("translated", (
                (self._get_rule(self.DAILY_RULE).id, 'test'),
            )),
            ("not translated", (
                (self._get_rule(self.UNTRANSLATED_DAILY_RULE).id, 'test', ''),
            )),
        )

        msgs = self._upload(data, headers)

        untrans_rule = self._get_rule(self.UNTRANSLATED_DAILY_RULE)
        self.assertEqual(msgs, [
            "Updated 0 rule(s) in 'translated' sheet",
            f"Error updating rule with id {untrans_rule.id} in 'not translated' sheet: Missing message",
            "Updated 0 rule(s) in 'not translated' sheet",
        ])
        daily_content = untrans_rule.get_schedule().memoized_events[0].content
        self.assertEqual(daily_content.message, {'*': 'Joan'})
