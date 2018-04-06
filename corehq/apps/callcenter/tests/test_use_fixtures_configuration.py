from __future__ import absolute_import
from __future__ import unicode_literals
import os

from django.test import SimpleTestCase

from corehq.apps.app_manager.models import ReportModule, ReportAppConfig
from corehq.apps.callcenter.app_parser import (
    parse_indicator, ParsedIndicator, get_call_center_config_from_app,
    _get_indicators_used_in_modules, _get_indicators_used_in_forms
)
from corehq.apps.callcenter import const
from corehq.apps.callcenter.tests.test_models import get_indicator_slugs_from_config
from corehq.apps.domain.models import Domain, CallCenterProperties
from corehq.apps.callcenter.fixturegenerators import IndicatorsFixturesProvider
from corehq.util.test_utils import generate_cases, TestFileMixin


class TestUseFixturesConfig(SimpleTestCase):

    def test_fixture_provider(self):
        provider = IndicatorsFixturesProvider()
        domain = Domain(
            call_center_config=CallCenterProperties(
                enabled=True,
                case_owner_id="bar",
                case_type="baz",
            )
        )

        domain.call_center_config.use_fixtures = False
        self.assertTrue(provider._should_return_no_fixtures(domain, None))

        domain.call_center_config.use_fixtures = True
        self.assertFalse(provider._should_return_no_fixtures(domain, None))


class TestIndicatorsFromApp(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    @property
    def test_indicators(self):
        return sorted([
            'cases_total_caregiver_month0',
            'cases_total_mother_month1',
            'cases_active_caregiver_month0',
            'cases_active_beneficiary_week1',
            'cases_opened_beneficiary_week1',
            'cases_closed_beneficiary_week0',
            'casesUpdatedMonth0',
            'formsSubmittedWeek0',
            'forms_submitted_month1',
            'totalCases',
            'motherFormsMonth0',
        ])

    def test_get_indicators_used_in_app_blank(self):
        app = self._get_app()

        indicators = list(
            _get_indicators_used_in_modules(app)
        )
        self.assertEqual(indicators, [])

    def test_get_indicators_used_in_modules(self):
        app = self._get_app()
        self._add_indicators_to_module_details(app.get_module(0), self.test_indicators[0:2])
        self._add_indicators_to_module_details(app.get_module(1), self.test_indicators[2:4])
        self._add_indicators_to_module_details(app.get_module(2), self.test_indicators[4:])

        indicators = sorted(list(
            _get_indicators_used_in_modules(app)
        ))
        self.assertEqual(indicators, self.test_indicators)

    def test_get_indicators_used_in_forms(self):
        app = self._get_app()
        forms = list(app.get_forms(bare=True))
        self._add_indicators_to_form(forms[0], self.test_indicators[0:2])
        self._add_indicators_to_form(forms[1], self.test_indicators[2:4], instance_name='cc_indicators')
        self._add_indicators_to_form(forms[2], self.test_indicators[4:])

        indicators = sorted(list(
            _get_indicators_used_in_forms(app)
        ))
        self.assertEqual(indicators, self.test_indicators)

    def test_get_config_from_app(self):
        app = self._get_app()
        app.domain = 'aarohi'
        self._add_indicators_to_module_details(app.get_module(0), self.test_indicators[0:2])
        self._add_indicators_to_module_details(app.get_module(1), self.test_indicators[2:4])
        forms = list(app.get_forms(bare=True))
        self._add_indicators_to_form(forms[2], self.test_indicators[4:])
        config = get_call_center_config_from_app(app)
        indicators_from_config = get_indicator_slugs_from_config(config)
        expected = self.test_indicators
        expected = sorted(
            # these get added becuase legacy indicators just use the date ranges for the
            # new indicator names
            expected + ['formsSubmittedMonth1', 'forms_submitted_week0']
        )
        self.assertEqual(
            sorted(indicators_from_config),
            expected
        )

    def test_get_config_from_app_report_module(self):
        app = self._get_app()
        report_module = app.add_module(ReportModule.new_module('Reports', None))
        report_module.report_configs = [
            ReportAppConfig(report_id='other_config_id', header={'en': 'CommBugz'})
        ]
        indicators = sorted(list(
            _get_indicators_used_in_modules(app)
        ))
        self.assertEqual(indicators, [])

    def _get_app(self):
        from corehq.apps.app_manager.tests.app_factory import AppFactory
        factory = AppFactory()
        factory.new_basic_module('m0', 'case1')
        factory.new_basic_module('m1', 'case2')
        factory.new_advanced_module('m2', 'case3')
        return factory.app

    def _add_indicators_to_module_details(self, module, indicators):
        module.case_details.short.columns.extend([
            _get_detail_column(indicator) for indicator in indicators
        ])

    def _add_indicators_to_form(self, form, indicators, instance_name='indicators'):

        def _get_bind(indicator):
            return """<bind
            nodeset="/data/question1"
            type="xsd:string"
            calculate="instance(\'{}\')/indicators/case[
                @id = instance(\'commcaresession\')/session/data/case_id
            ]/{}"/>
            """.format(instance_name, indicator)

        form_template = self.get_xml('form_template')
        instance = '<instance id="{}" src="jr://fixture/indicators:call-center" />'.format(instance_name)
        form.source = form_template.format(
            instance=instance,
            binds=''.join([
                _get_bind(indicator) for indicator in indicators
            ])
        )


@generate_cases([
    ('cases_total_caregiver_month0', (const.CASES_TOTAL, 'caregiver', const.MONTH0, False)),
    ('cases_total_mother_month1', (const.CASES_TOTAL, 'mother', const.MONTH1, False)),
    ('cases_active_week0', (const.CASES_ACTIVE, None, const.WEEK0, False)),
    ('cases_total_month0', (const.CASES_TOTAL, None, const.MONTH0, False)),
    ('cases_active_caregiver_month0', (const.CASES_ACTIVE, 'caregiver', const.MONTH0, False)),
    ('cases_active_beneficiary_week1', (const.CASES_ACTIVE, 'beneficiary', const.WEEK1, False)),
    ('cases_opened_beneficiary_week1', (const.CASES_OPENED, 'beneficiary', const.WEEK1, False)),
    ('cases_closed_beneficiary_week0', (const.CASES_CLOSED, 'beneficiary', const.WEEK0, False)),
    ('casesUpdatedMonth0', (const.CASES_ACTIVE, None, const.MONTH0, True)),
    ('formsSubmittedWeek0', (const.FORMS_SUBMITTED, None, const.WEEK0, True)),
    ('forms_submitted_month1', (const.FORMS_SUBMITTED, None, const.MONTH1, False)),
    ('totalCases', (const.CASES_TOTAL, None, None, True)),
    ('motherFormsMonth0', (const.CUSTOM_FORM, 'motherForms', const.MONTH0, False)),
    ('motherFormsMonth0)', None),
], TestIndicatorsFromApp)
def test_parse_indicator(self, indicator_name, parsed_tuple):
    expected = ParsedIndicator(*parsed_tuple) if parsed_tuple else parsed_tuple
    self.assertEqual(
        parse_indicator(indicator_name, const.PER_DOMAIN_FORM_INDICATORS['aarohi']),
        expected
    )


@generate_cases([
    (['FindPatientFormsMonth0', 'FindPatientFormsMonth1)'], ['FindPatientFormsMonth0']),  # custom
    (['formsSubmittedWeek0', 'formsSubmittedWek1'], ['formsSubmittedWeek0']),  # legacy bad period
    (['formsSubmittedWeek0', 'formsSubmitedWeek1'], ['formsSubmittedWeek0']),  # legacy bad indicator name
    (['cases_active_week0', 'cases_active_wek1'], ['cases_active_week0']),  # bad period
    (['cases_active_week0', 'cases_ative_week1'], ['cases_active_week0']),  # pad indicator name
], TestIndicatorsFromApp)
def test_get_config_from_app_bad_names(self, indicators, expected):
    app = self._get_app()
    app.domain = 'infomovel'
    self._add_indicators_to_module_details(app.get_module(0), indicators=indicators)
    config = get_call_center_config_from_app(app)
    indicators_from_config = get_indicator_slugs_from_config(config)
    self.assertEqual(
        sorted(indicators_from_config),
        expected
    )


def _get_detail_column(indicator_name):
    from corehq.apps.app_manager.models import DetailColumn
    return DetailColumn(
        header={"en": "i1"},
        model="case",
        field="indicator:cc/{}".format(indicator_name),
        format="plain")
