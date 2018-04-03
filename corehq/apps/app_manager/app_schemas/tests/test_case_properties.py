from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import SimpleTestCase
from mock import patch, MagicMock
from corehq.apps.app_manager.app_schemas.case_properties import get_case_properties
from corehq.apps.app_manager.models import Module, AdvancedModule, FormSchedule, \
    ScheduleVisit
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin


@patch('corehq.apps.app_manager.app_schemas.case_properties.get_per_type_defaults', MagicMock(return_value={}))
class GetCasePropertiesTest(SimpleTestCase, TestXmlMixin):
    file_path = ('data',)

    def assertCaseProperties(self, app, case_type, expected_properties):
        properties = get_case_properties(app, [case_type])
        self.assertEqual(
            set(properties[case_type]),
            set(expected_properties),
        )

    def test_basic_apps(self):
        for class_ in (Module, AdvancedModule):
            factory = AppFactory()
            m1, m1f1 = factory.new_module(class_, 'open_case', 'house')
            factory.form_opens_case(m1f1)
            m1f2 = factory.new_form(m1)
            factory.form_requires_case(m1f2, case_type='house', update={
                'foo': '/data/question1',
                'bar': '/data/question2',
            })
            self.assertCaseProperties(factory.app, 'house', ['foo', 'bar'])

    def test_scheduler_module(self):
        factory = AppFactory()
        m1, m1f1 = factory.new_basic_module('open_case', 'house')
        factory.form_opens_case(m1f1)
        m2, m2f1 = factory.new_advanced_module('scheduler_module', 'house')
        m2f2 = factory.new_form(m2)
        factory.form_requires_case(m2f1, case_type='house', update={
            'foo': '/data/question1',
            'bar': '/data/question2',
        })
        factory.form_requires_case(m2f2, case_type='house', update={
            'bleep': '/data/question1',
            'bloop': '/data/question2',
        })

        self._add_scheduler_to_module(m2)
        self._add_scheduler_to_form(m2f1, m2, 'form1')
        self._add_scheduler_to_form(m2f2, m2, 'form2')

        self.assertCaseProperties(factory.app, 'house', [
            'foo',
            'bar',
            'bleep',
            'bloop',
            # Scheduler properties:
            'last_visit_date_form1',
            'last_visit_number_form1',
            'last_visit_date_form2',
            'last_visit_number_form2',
            'current_schedule_phase',
        ])

    def _add_scheduler_to_module(self, module):
        # (this mimics the behavior in app_manager.views.schedules.edit_schedule_phases()
        module.update_schedule_phase_anchors([(1, 'date-opened')])
        module.update_schedule_phases(['date-opened'])
        module.has_schedule = True

    def _add_scheduler_to_form(self, form, module, form_abreviation):
        # (this mimics the behavior in app_manager.views.schedules.edit_visit_schedule()
        # A Form.source is required to retreive scheduler properties
        form.source = self.get_xml('very_simple_form')
        phase, _ = module.get_or_create_schedule_phase(anchor='date-opened')
        form.schedule_form_id = form_abreviation
        form.schedule = FormSchedule(
            starts=5,
            expires=None,
            visits=[
                ScheduleVisit(due=7, expires=5, starts=-2),
            ]
        )
        phase.add_form(form)
