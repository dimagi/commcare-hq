from mock import patch
from django.test import SimpleTestCase
from corehq.apps.app_manager.models import (
    DetailColumn,
    Application,
    FormSchedule,
    ScheduleVisit,
    SchedulePhase,
)
from corehq.apps.app_manager.exceptions import ScheduleError
from corehq.apps.app_manager.tests.util import TestFileMixin


class ScheduleTest(SimpleTestCase, TestFileMixin):
    file_path = ('data', 'suite')

    def setUp(self):
        self.is_usercase_in_use_patch = patch('corehq.apps.app_manager.models.is_usercase_in_use')
        self.is_usercase_in_use_mock = self.is_usercase_in_use_patch.start()
        self.is_usercase_in_use_mock.return_value = True
        self.app = Application.wrap(self.get_json('suite-advanced'))

        self.module = self.app.get_module(1)
        self.module.has_schedule = True
        self.form_1 = self.module.get_form(0)
        self.form_2 = self.module.get_form(1)
        self.form_3 = self.module.get_form(2)

        self.form_1.schedule = FormSchedule(
            expires=120,
            post_schedule_increment=15,
            visits=[
                ScheduleVisit(due=5, late_window=4),
                ScheduleVisit(due=10, late_window=9),
                ScheduleVisit(due=20, late_window=5)
            ]
        )

        self.form_2.schedule = FormSchedule(
            visits=[
                ScheduleVisit(due=7, late_window=4),
                ScheduleVisit(due=15)
            ]
        )

        self.form_3.schedule = FormSchedule(
            visits=[
                ScheduleVisit(due=9, late_window=1),
                ScheduleVisit(due=11)
            ]
        )

        self.module.case_details.short.columns.append(
            DetailColumn(
                header={'en': 'Next due'},
                model='case',
                field='schedule:nextdue',
                format='plain',
            )
        )

    def test_get_phase(self):
        phase = SchedulePhase(
            anchor='some_case_property',
            forms=[self.form_1, self.form_2],
        )

        self.module.schedule_phases = [phase]

        self.assertEqual(self.form_1.get_phase(), phase)
        self.assertEqual(self.form_3.get_phase(), None)

    def test_phase_requires_anchor(self):
        self.module.schedule_phases = [
            SchedulePhase(
                forms=[self.form_3]
            ),
        ]
        with self.assertRaises(ScheduleError):
            self.app.create_suite()

    def test_schedule_detail(self):
        self.module.schedule_phases = [
            SchedulePhase(  # phase 1
                anchor='edd',
                forms=[self.form_1, self.form_2],
            ),
            SchedulePhase(  # phase 2
                anchor='dob',
                forms=[self.form_3]
            ),
        ]

        suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('schedule-entry'), suite, "./detail[@id='m1_case_short']")
