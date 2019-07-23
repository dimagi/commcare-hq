# encoding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from mock import patch
import copy
from django.test import SimpleTestCase
from corehq.apps.app_manager.schemas.document.form_action import (
    FormActionCondition,
)
from corehq.apps.app_manager.models import (
    DetailColumn,
    Application,
    FormSchedule,
    ScheduleVisit,
    SchedulePhase,
    SchedulePhaseForm,
)
from corehq.apps.app_manager.exceptions import ScheduleError
from corehq.apps.app_manager.tests.util import TestXmlMixin


class ScheduleTest(SimpleTestCase, TestXmlMixin):
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

        self._add_form_abbreviations()
        self._add_form_schedules()
        self._add_form_detail_variable()

    def _add_form_abbreviations(self):
        self.form_1.schedule_form_id = "हिन्दी"
        self.form_2.schedule_form_id = "a983e9"
        self.form_3.schedule_form_id = "39f0ea"

    def _add_form_schedules(self):
        self.form_1.schedule = FormSchedule(
            expires=120,
            starts=-5,
            visits=[
                ScheduleVisit(due=5, expires=4, starts=-5),
                ScheduleVisit(due=10, expires=9),
                ScheduleVisit(starts=5, expires=100, repeats=True, increment=15)
            ]
        )

        self.form_2.schedule = FormSchedule(
            allow_unscheduled=True,
            visits=[
                ScheduleVisit(due=7, expires=4),
                ScheduleVisit(due=15)
            ]
        )

        self.form_3.schedule = FormSchedule(
            visits=[
                ScheduleVisit(due=9, expires=1),
                ScheduleVisit(due=11)
            ]
        )

    def _add_form_detail_variable(self):
        self.module.case_details.short.columns.append(
            DetailColumn(
                header={'en': 'Next due'},
                model='case',
                field='schedule:nextdue',
                format='plain',
            )
        )

    def tearDown(self):
        self.is_usercase_in_use_patch.stop()

    def _apply_schedule_phases(self):
        self.module.schedule_phases = [
            SchedulePhase(  # phase 1
                anchor='edd',
                forms=[SchedulePhaseForm(form_id=self.form_1.unique_id),
                       SchedulePhaseForm(form_id=self.form_2.unique_id)],
            ),
            SchedulePhase(  # phase 2
                anchor='dob',
                forms=[SchedulePhaseForm(form_id=self.form_3.unique_id)]
            ),
        ]

    def test_get_phase(self):
        phase = SchedulePhase(
            anchor='some_case_property',
            forms=[SchedulePhaseForm(form_id=self.form_1.unique_id),
                   SchedulePhaseForm(form_id=self.form_2.unique_id)],
        )

        self.module.schedule_phases = [phase]

        self.assertEqual(self.form_1.get_phase(), phase)
        self.assertEqual(self.form_3.get_phase(), None)

    def test_phase_requires_anchor(self):
        self.module.schedule_phases = [
            SchedulePhase(
                forms=[SchedulePhaseForm(form_id=self.form_3.unique_id)]
            ),
        ]
        with self.assertRaises(ScheduleError):
            self.app.create_suite()

    def test_get_or_create_schedule_phase(self):
        pre_made_phase = SchedulePhase(anchor='sea-floor')
        self.module.schedule_phases = [pre_made_phase]

        phase, created = self.module.get_or_create_schedule_phase(anchor='hook')
        self.assertTrue(created)

        phase_2, created = self.module.get_or_create_schedule_phase(anchor='sea-floor')
        self.assertFalse(created)
        self.assertEqual(phase_2, pre_made_phase)

        with self.assertRaises(ScheduleError):
            self.module.get_or_create_schedule_phase(anchor='  \n\n\n\t\t')

        with self.assertRaises(ScheduleError):
            self.module.get_or_create_schedule_phase(anchor=None)

    def test_update_schedule_phases(self):
        pre_made_phase = SchedulePhase(anchor='foo')
        pre_made_phase_2 = SchedulePhase(anchor='bar')
        self.module.schedule_phases = [pre_made_phase, pre_made_phase_2]

        new_phase = SchedulePhase(anchor='baz')
        updated_phases = [new_phase.anchor, pre_made_phase.anchor]

        self.module.update_schedule_phases(updated_phases)
        self.assertEqual([phase.anchor for phase in self.module.get_schedule_phases()], updated_phases)

        # Test reordering
        self.module.schedule_phases = [pre_made_phase, pre_made_phase_2]
        updated_phases = [pre_made_phase_2.anchor, pre_made_phase.anchor]
        self.module.update_schedule_phases(updated_phases)
        self.assertEqual([phase.anchor for phase in self.module.get_schedule_phases()], updated_phases)

        # Test deletion
        self.module.schedule_phases = [pre_made_phase, pre_made_phase_2]
        updated_phases = []
        self.module.update_schedule_phases(updated_phases)
        self.assertEqual([phase.anchor for phase in self.module.get_schedule_phases()], updated_phases)

        # Test deletion with forms
        phase_with_forms = SchedulePhase(
            anchor='edd',
            forms=[SchedulePhaseForm(form_id=self.form_1.unique_id)],
        )
        self.module.schedule_phases = [phase_with_forms]
        updated_phases = []
        with self.assertRaises(ScheduleError):
            self.module.update_schedule_phases(updated_phases)

    def test_update_schedule_phase_anchors(self):
        pre_made_phase = SchedulePhase(anchor='foo',
                                       forms=[SchedulePhaseForm(form_id=self.form_1.unique_id)],)
        pre_made_phase_2 = SchedulePhase(anchor='bar',
                                         forms=[SchedulePhaseForm(form_id=self.form_2.unique_id)])
        pre_made_phase_3 = SchedulePhase(anchor='burp')
        self.module.schedule_phases = [pre_made_phase, pre_made_phase_2, pre_made_phase_3]

        new_anchors = [(2, 'baz'), (1, 'quux')]

        self.module.update_schedule_phase_anchors(new_anchors)
        self.assertEqual(self.module.schedule_phases[0].forms[0].form_id, self.form_1.unique_id)
        self.assertEqual(self.module.schedule_phases[0].anchor, new_anchors[1][1])

        self.assertEqual(self.module.schedule_phases[1].forms[0].form_id, self.form_2.unique_id)
        self.assertEqual(self.module.schedule_phases[1].anchor, new_anchors[0][1])

        self.assertEqual(self.module.schedule_phases[2].anchor, 'burp')

    def test_form_in_phase_requires_schedule(self):
        self._apply_schedule_phases()
        self.form_3.schedule = None
        with self.assertRaises(ScheduleError):
            self.app.create_suite()

        self.module.schedule_phases.pop()
        self.app.create_suite()

    def test_remove_form_from_phase(self):
        form_1 = self.form_1
        form_2 = self.form_2
        self.module.schedule_phases = [
            SchedulePhase(
                anchor='dob',
                forms=[SchedulePhaseForm(form_id=form_1.unique_id),
                       SchedulePhaseForm(form_id=form_2.unique_id)]
            )
        ]
        phase = next(self.module.get_schedule_phases())  # get the phase through the module so we have a _parent
        phase.remove_form(form_1)

        self.assertEqual(len(phase.forms), 1)
        self.assertEqual([form_2], list(phase.get_forms()))

        with self.assertRaises(ScheduleError):
            phase.remove_form(form_1)

    def test_add_form_to_phase(self):
        self.module.schedule_phases = [
            SchedulePhase(
                anchor='dob',
                forms=[SchedulePhaseForm(form_id=self.form_1.unique_id),
                       SchedulePhaseForm(form_id=self.form_2.unique_id)]
            ),
            SchedulePhase(anchor='second_phase', forms=[]),
        ]
        phases = list(self.module.get_schedule_phases())
        phase1 = phases[0]
        phase1.add_form(self.form_3)
        self.assertEqual(phase1.get_phase_form_index(self.form_3), 2)

        # adding a form to a different phase removes it from the first phase
        phase2 = phases[1]
        phase2.add_form(self.form_3)
        self.assertEqual(phase2.get_phase_form_index(self.form_3), 0)
        self.assertIsNone(phase1.get_form(self.form_3))

    def test_schedule_detail(self):
        self._apply_schedule_phases()

        suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('schedule-entry'), suite, "./detail[@id='m1_case_short']")

    def test_schedule_fixture(self):
        self._apply_schedule_phases()

        suite = self.app.create_suite()
        self.assertXmlPartialEqual(self.get_xml('schedule-fixture'), suite, './fixture')

    def test_multiple_modules(self):
        self._apply_schedule_phases()

        other_module = self.app.get_module(2)
        other_module.has_schedule = True
        scheduled_form = other_module.get_form(0)
        scheduled_form.schedule = FormSchedule(
            visits=[
                ScheduleVisit(due=9),
                ScheduleVisit(due=11)
            ]
        )
        other_module.forms.append(copy.copy(scheduled_form))

        other_module.schedule_phases = [
            SchedulePhase(
                anchor='case_property',
                forms=[SchedulePhaseForm(form_id=scheduled_form.unique_id)]
            )
        ]

        expected_fixture = """
             <partial>
             <fixture id="schedule:m2:p1:f0">
                 <schedule expires="" allow_unscheduled="False">
                     <visit id="1" due="9" repeats="False"/>
                     <visit id="2" due="11" repeats="False"/>
                 </schedule>
             </fixture>
             </partial>
        """

        suite = self.app.create_suite()

        self.assertXmlPartialEqual(expected_fixture, suite, './fixture[@id="schedule:m2:p1:f0"]')
        self.assertXmlHasXpath(suite, './fixture[@id="schedule:m1:p1:f0"]')

    def test_form_filtering(self):
        self._apply_schedule_phases()
        suite = self.app.create_suite()
        form_ids = (self.form_1.schedule_form_id, self.form_2.schedule_form_id)
        case_load_actions = ["case_id_case_clinic", "case_id_load_clinic0"]
        case = ["instance('casedb')/casedb/case[@case_id=instance('commcaresession')/session/data/{}]"
                .format(action) for action in case_load_actions]
        for form_num, form_id in enumerate(form_ids):
            anchor = "{case}/edd".format(case=case[form_num])
            current_schedule_phase = "{case}/current_schedule_phase".format(case=case[form_num])
            visit = "instance('schedule:m1:p1:f{form_num}')/schedule/visit".format(form_num=form_num)
            schedule = "instance('schedule:m1:p1:f{form_num}')/schedule".format(form_num=form_num)

            current_phase_query = (
                "({current_schedule_phase} = '' or {current_schedule_phase} = 1)"
            ).format(current_schedule_phase=current_schedule_phase)

            within_form_relevancy = (
                "today() &gt;= (date({anchor}) + int({schedule}/@starts)) and "
                "({schedule}/@expires = '' or today() &lt;= (date({anchor}) + int({schedule}/@expires)))"
            ).format(schedule=schedule, anchor=anchor)

            next_valid_schedules = (
                "{current_phase_query} and "
                "{anchor} != '' and "
                "({within_form_relevancy})"
            ).format(current_phase_query=current_phase_query, anchor=anchor,
                     within_form_relevancy=within_form_relevancy)

            allow_unscheduled = (
                "{schedule}/@allow_unscheduled = 'True'"
            ).format(schedule=schedule)

            upcoming_scheduled_visits = (
                "{visit}"
                "[{case}/last_visit_number_{form_id} = '' or "
                    "if(@repeats = 'True', @id &gt;= {case}/last_visit_number_{form_id},"
                        " @id &gt; {case}/last_visit_number_{form_id})]"
                "[if(@repeats = 'True', "
                    "today() &gt;= (date({case}/last_visit_date_{form_id}) + int(@increment) + int(@starts)) and "  # noqa
                        "(@expires = '' or today() &lt;= (date({case}/last_visit_date_{form_id}) + int(@increment)"  # noqa
                        " + int(@expires))), "
                    "today() &gt;= (date({anchor}) + int(@due) + int(@starts)) and "
                        "(@expires = '' or today() &lt;= (date({anchor}) + int(@due) + int(@expires)))"
                ")]"
            ).format(visit=visit, case=case[form_num], form_id=form_id, anchor=anchor)

            visit_allowed = (
                "{allow_unscheduled} or "
                "count({upcoming_scheduled_visits}) &gt; 0"
            ).format(allow_unscheduled=allow_unscheduled, upcoming_scheduled_visits=upcoming_scheduled_visits)

            filter_condition = (
                "({next_valid_schedules}) and ({visit_allowed})"
            ).format(next_valid_schedules=next_valid_schedules, visit_allowed=visit_allowed)

            partial = """
            <partial>
                <command id='m1-f{form_num}' relevant="{filter_condition}" />
            </partial>
            """.format(form_num=form_num, filter_condition=filter_condition)

            self.assertXmlPartialEqual(partial, suite, './menu/command[@id="m1-f{}"]'.format(form_num))

    # xmlns is added because I needed to use WrappedNode.find() in the next few tests
    xmlns = ("xmlns='http://www.w3.org/2002/xforms' "
             "xmlns:h='http://www.w3.org/1999/xhtml' "
             "xmlns:jr='http://openrosa.org/javarosa' "
             "xmlns:orx='http://openrosa.org/jr/xforms' "
             "xmlns:xsd='http://www.w3.org/2001/XMLSchema'")

    def test_current_schedule_phase(self):
        """ Current Schedule Phase is set depending on transition and termination conditions """
        current_schedule_phase_partial = """
        <partial>
            <bind type="xs:integer"
                  nodeset="/data/case_case_clinic/case/update/current_schedule_phase"
                  calculate="{value}"
            {xmlns}/>
        </partial>
        """
        transition_question = '/data/successful_birth'
        transition_answer = 'yes'
        self.form_1.schedule.transition_condition = FormActionCondition(
            type='if',
            question=transition_question,
            answer=transition_answer,
        )

        termination_question = '/data/passed_away'
        termination_answer = 'yes'
        self.form_1.schedule.termination_condition = FormActionCondition(
            type='if',
            question=termination_question,
            answer=termination_answer,
        )

        self._apply_schedule_phases()

        xform_1 = self.form_1.wrapped_xform()
        self.form_1.add_stuff_to_xform(xform_1)
        value = "if({termination_condition}, -1, if({transition_condition}, 2, 1))".format(
            termination_condition="{} = '{}'".format(termination_question, termination_answer),
            transition_condition="{} = '{}'".format(transition_question, transition_answer),
        )
        self.assertXmlPartialEqual(
            current_schedule_phase_partial.format(value=value, xmlns=self.xmlns),
            (xform_1.model_node.find(
                './bind[@nodeset="/data/case_case_clinic/case/update/current_schedule_phase"]')
             .render()),
            '.'
        )

    def test_current_schedule_phase_no_transitions(self):
        """The current_schedule_phase is set to the phase of the current form"""
        self._apply_schedule_phases()

        current_schedule_phase_partial = """
        <partial>
            <bind type="xs:integer"
                  nodeset="/data/case_load_clinic0/case/update/current_schedule_phase"
                  calculate="{value}"
            {xmlns}/>
        </partial>
        """
        value = "if(false(), -1, if(false(), 2, {}))".format(self.form_2.get_phase().id)
        xform_2 = self.form_2.wrapped_xform()
        self.form_2.add_stuff_to_xform(xform_2)
        self.assertXmlPartialEqual(
            current_schedule_phase_partial.format(value=value, xmlns=self.xmlns),
            (xform_2.model_node.find(
                './bind[@nodeset="/data/case_load_clinic0/case/update/current_schedule_phase"]')
             .render()),
            '.'
        )

    def test_last_visit_number(self):
        """ Increment the visit number for that particular form. If it is empty, set it to 1 """
        last_visit_number_partial = """
        <partial>
            <bind nodeset="/data/case_case_clinic/case/update/last_visit_number_{form_id}"
                  calculate="/data/current_visit_number"
                  relevant="not(/data/unscheduled_visit)"
            {xmlns}/>
        </partial>
        """
        self._apply_schedule_phases()
        xform_1 = self.form_1.wrapped_xform()
        form_id = self.form_1.schedule_form_id
        self.form_1.add_stuff_to_xform(xform_1)
        self.assertXmlPartialEqual(
            last_visit_number_partial.format(form_id=form_id, xmlns=self.xmlns),
            (xform_1.model_node.find('./bind[@nodeset="/data/case_case_clinic/case/update/last_visit_number_{}"]'
                                     .format(form_id)).render()),
            '.'
        )

    def test_last_visit_date(self):
        """ Set the date of the last visit when a form gets submitted """
        last_visit_date_partial = """
        <partial>
            <bind nodeset="/data/case_case_clinic/case/update/last_visit_date_{form_id}"
                  type="xsd:dateTime"
                  calculate="/data/meta/timeEnd"
                  relevant="not(/data/unscheduled_visit)"
            {xmlns}/>
        </partial>
        """
        self._apply_schedule_phases()
        xform_1 = self.form_1.wrapped_xform()
        form_id = self.form_1.schedule_form_id
        self.form_1.add_stuff_to_xform(xform_1)
        self.assertXmlPartialEqual(
            last_visit_date_partial.format(form_id=form_id, xmlns=self.xmlns),
            (xform_1.model_node.find('./bind[@nodeset="/data/case_case_clinic/case/update/last_visit_date_{}"]'
                                     .format(form_id)).render()),
            '.'
        )

    def test_next_visit_date(self):
        """ add next_visit_date to each form """
        next_visit_date_partial = """
        <partial>
            <bind nodeset="/data/next_visit_date"
                  calculate="date(min({form_names}))"
            {xmlns}/>
        </partial>
        """
        self._apply_schedule_phases()
        phase_forms = [self.form_1, self.form_2]
        xform_1 = self.form_1.wrapped_xform()
        self.form_1.add_stuff_to_xform(xform_1)
        form_names = ["/data/next_{}".format(f.schedule_form_id) for f in phase_forms]

        self.assertXmlPartialEqual(
            next_visit_date_partial.format(form_names=",".join(form_names), xmlns=self.xmlns),
            xform_1.model_node.find('./bind[@nodeset="/data/next_visit_date"]').render(),
            '.'
        )

        for form in phase_forms:
            self.assertTrue(
                len(xform_1.model_node.find("./bind[@nodeset='/data/next_{}']"
                                            .format(form.schedule_form_id)).render())
                > 0)
