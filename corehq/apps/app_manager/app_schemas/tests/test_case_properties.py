import doctest

from django.test import SimpleTestCase

from unittest.mock import MagicMock, patch

import corehq.apps.app_manager.app_schemas.case_properties
from corehq.apps.app_manager.app_schemas.case_properties import (
    _CaseRelationshipManager,
    _CaseTypeEquivalence,
    _CaseTypeRef,
    get_case_properties,
)
from corehq.apps.app_manager.models import (
    AdvancedModule,
    FormSchedule,
    Module,
    ScheduleVisit,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin


@patch('corehq.apps.app_manager.app_schemas.case_properties.get_per_type_defaults', MagicMock(return_value={}))
@patch('corehq.apps.app_manager.app_schemas.case_properties.domain_has_privilege', MagicMock(return_value=False))
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

    def test_case_sharing(self):
        factory1 = AppFactory()
        factory2 = AppFactory()
        factory1.app.case_sharing = True
        factory2.app.case_sharing = True

        with patch('corehq.apps.app_manager.app_schemas.case_properties.get_case_sharing_apps_in_domain')\
                as mock_sharing:
            mock_sharing.return_value = [factory1.app, factory2.app]
            a1m1, a1m1f1 = factory1.new_basic_module('open_patient', 'patient')
            factory1.form_requires_case(a1m1f1, update={
                'app1': 'yes',
            })
            a2m1, a2m1f1 = factory2.new_basic_module('open_patient', 'patient')
            factory1.form_requires_case(a2m1f1, update={
                'app2': 'yes',
            })
            self.assertCaseProperties(factory1.app, 'patient', ['app1', 'app2'])

    def test_parent_child_properties(self):
        factory = AppFactory()

        household_module, houshold_form_1 = factory.new_basic_module('household_module', 'household')
        patient_module, patient_form_1 = factory.new_basic_module('patient_module', 'patient')
        referral_module, referral_form_1 = factory.new_basic_module('referral_module', 'referral')
        factory.form_requires_case(houshold_form_1, 'household', update={
            'household_name': 'HH',
        })
        factory.form_opens_case(houshold_form_1, 'patient', is_subcase=True)
        factory.form_requires_case(patient_form_1, update={
            'patient_id': '1',
            'parent/household_id': '1',
        })
        factory.form_opens_case(patient_form_1, 'referral', is_subcase=True)
        factory.form_requires_case(referral_form_1, update={
            'parent/patient_name': "Ralph",
            'parent/parent/household_color': 'green',
            'referral_id': '1',
        })
        self.assertCaseProperties(factory.app, 'household', [
            'household_color',
            'household_id',
            'household_name',
        ])
        self.assertCaseProperties(factory.app, 'patient', [
            'parent/household_color',
            'parent/household_id',
            'parent/household_name',
            'patient_id',
            'patient_name',
        ])
        self.assertCaseProperties(factory.app, 'referral', [
            'parent/parent/household_color',
            'parent/parent/household_id',
            'parent/parent/household_name',
            'parent/patient_id',
            'parent/patient_name',
            'referral_id',
        ])

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
        form.source = self.get_xml('very_simple_form').decode('utf-8')
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


class TestCycle(SimpleTestCase):
    def test_cycle(self):
        all_possible_equivalences = _CaseRelationshipManager(parent_type_map={
            'ccs_record': {'parent': ['person']},
            'person': {'parent': ['ccs_record', 'person']},
        })._all_possible_equivalences
        self.assertEqual(all_possible_equivalences, {
            _CaseTypeEquivalence('ccs_record', _CaseTypeRef('ccs_record', ('parent', 'parent'))),
            _CaseTypeEquivalence('ccs_record', _CaseTypeRef('ccs_record', ())),
            _CaseTypeEquivalence('ccs_record', _CaseTypeRef('person', ('parent', 'parent'))),
            _CaseTypeEquivalence('ccs_record', _CaseTypeRef('person', ('parent',))),
            _CaseTypeEquivalence('person', _CaseTypeRef('ccs_record', ('parent',))),
            _CaseTypeEquivalence('person', _CaseTypeRef('person', ('parent', 'parent'))),
            _CaseTypeEquivalence('person', _CaseTypeRef('person', ('parent',))),
            _CaseTypeEquivalence('person', _CaseTypeRef('person', ())),
        })


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.apps.app_manager.app_schemas.case_properties)
        self.assertEqual(results.failed, 0)
