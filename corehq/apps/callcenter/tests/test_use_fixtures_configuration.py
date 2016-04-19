from django.test import SimpleTestCase

from corehq.apps.callcenter.app_parser import get_indicators_used_in_app, parse_indicator, ParsedIndicator, \
    get_call_center_config_from_app
from corehq.apps.callcenter.const import CASES_TOTAL, CASES_CLOSED, CASES_OPENED, CASES_ACTIVE, MONTH0, MONTH1, WEEK1, \
    WEEK0, FORMS_SUBMITTED
from corehq.apps.callcenter.tests import get_indicator_slugs_from_config
from corehq.apps.domain.models import Domain, CallCenterProperties
from corehq.apps.callcenter.fixturegenerators import IndicatorsFixturesProvider
from corehq.util.test_utils import generate_cases


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


class TestIndicatorsFromApp(SimpleTestCase):
    
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
        ])
    
    def test_get_indicators_from_app(self):
        app = self._build_app()

        indicators = sorted(list(
            get_indicators_used_in_app(app)
        ))
        self.assertEqual(indicators, self.test_indicators)

    def test_get_config_from_app(self):
        app = self._build_app()
        config = get_call_center_config_from_app(app)
        indicators_from_config = get_indicator_slugs_from_config(config)
        self.assertEqual(
            sorted(indicators_from_config),
            self.test_indicators
        )

    def _build_app(self):
        from corehq.apps.app_manager.tests.app_factory import AppFactory
        factory = AppFactory()
        m0 = factory.new_basic_module('m0', 'case1', with_form=False)
        m1 = factory.new_basic_module('m1', 'case2', with_form=False)
        m2 = factory.new_advanced_module('m2', 'case3', with_form=False)
        m0.case_details.short.columns.extend([
            _get_detail_column(self.test_indicators[0]),
            _get_detail_column(self.test_indicators[1]),
        ])
        m1.case_details.long.columns.extend([
            _get_detail_column(self.test_indicators[2]),
            _get_detail_column(self.test_indicators[3]),
        ])
        for indicator in self.test_indicators[4:]:
            m2.case_details.short.columns.append(
                _get_detail_column(indicator)
            )
        return factory.app


@generate_cases([
    ('cases_total_caregiver_month0', (CASES_TOTAL, 'caregiver', MONTH0, False)),
    ('cases_total_mother_month1', (CASES_TOTAL, 'mother', MONTH1, False)),
    ('cases_active_week0', (CASES_ACTIVE, None, WEEK0, False)),
    ('cases_total_month0', (CASES_TOTAL, None, MONTH0, False)),
    ('cases_active_caregiver_month0', (CASES_ACTIVE, 'caregiver', MONTH0, False)),
    ('cases_active_beneficiary_week1', (CASES_ACTIVE, 'beneficiary', WEEK1, False)),
    ('cases_opened_beneficiary_week1', (CASES_OPENED, 'beneficiary', WEEK1, False)),
    ('cases_closed_beneficiary_week0', (CASES_CLOSED, 'beneficiary', WEEK0, False)),
    ('casesUpdatedMonth0', (CASES_ACTIVE, None, MONTH0, True)),
    ('formsSubmittedWeek0', (FORMS_SUBMITTED, None, WEEK0, True)),
    ('forms_submitted_month1',(FORMS_SUBMITTED, None, MONTH1, False)),
    ('totalCases', (CASES_TOTAL, None, None, True)),
    ('motherFormsMonth0', ('custom', None, None, True)),
], TestIndicatorsFromApp)
def test_parse_indicator(self, indicator_name, parsed_tuple):
    self.assertEqual(
        parse_indicator(indicator_name),
        ParsedIndicator(*parsed_tuple)
    )


def _get_detail_column(indicator_name):
    from corehq.apps.app_manager.models import DetailColumn
    return DetailColumn(
        header={"en": "i1"},
        model="case",
        field="indicator:cc/{}".format(indicator_name),
        format="plain")
