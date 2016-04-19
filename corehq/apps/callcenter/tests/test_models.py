from corehq.apps.callcenter import const
from corehq.apps.callcenter.const import WEEK1, WEEK0, MONTH0
from corehq.apps.callcenter.models import (
    TypedIndicator, BasicIndicator, ByTypeWithTotal, CallCenterIndicatorConfig
)
from django.test import SimpleTestCase


def get_indicator_slugs_from_config(config):
    def legacy_slugs(key, indicator_conf):
        for date_range in indicator_conf.date_ranges:
            yield '{}{}'.format(key, date_range.title())

    def basic_slugs(key, indicator_conf):
        for date_range in indicator_conf.date_ranges:
            yield '{}_{}'.format(key, date_range)

    def typed_slugs(key, type_, indicator_conf):
        for date_range in indicator_conf.date_ranges:
            yield '{}_{}_{}'.format(key, type_, date_range)

    slugs = []
    if config.forms_submitted.enabled:
        slugs.extend(basic_slugs(const.FORMS_SUBMITTED, config.forms_submitted))

    for key in ['cases_total', 'cases_active', 'cases_opened', 'cases_closed']:
        indicator_config = getattr(config, key)
        if indicator_config.totals.enabled:
            slugs.extend(basic_slugs(key, indicator_config.totals))

        for type_config in indicator_config.by_type:
            if type_config.enabled:
                slugs.extend(typed_slugs(key, type_config.type, type_config))

    if config.legacy_forms_submitted.enabled:
        slugs.extend(legacy_slugs(const.LEGACY_FORMS_SUBMITTED, config.legacy_forms_submitted))
    if config.legacy_cases_total.enabled:
        slugs.append(const.LEGACY_TOTAL_CASES)
    if config.legacy_cases_active.enabled:
        slugs.extend(legacy_slugs(const.LEGACY_CASES_UPDATED, config.legacy_cases_active))
    return slugs


class ModelTests(SimpleTestCase):
    def test_types_by_date_range(self):
        by_type = ByTypeWithTotal(by_type=[
            TypedIndicator(enabled=True, date_ranges={WEEK0, WEEK1}, type='dog'),
            TypedIndicator(enabled=True, date_ranges={WEEK0}, type='cat'),
            TypedIndicator(enabled=True, date_ranges={WEEK1}, type='canary'),
            TypedIndicator(enabled=True, date_ranges={WEEK1, MONTH0}, type='fish'),
            TypedIndicator(enabled=False, date_ranges={MONTH0}, type='whale'),
        ])

        self.assertEqual(by_type.types_by_date_range(), {
            WEEK0: {'dog', 'cat'},
            WEEK1: {'dog', 'canary', 'fish'},
            MONTH0: {'fish'},
        })

    def test_real_example(self):
        config = CallCenterIndicatorConfig(
            domain='domain',
            forms_submitted=BasicIndicator(enabled=True, date_ranges={MONTH0}),
            cases_total=ByTypeWithTotal(
                totals=BasicIndicator(enabled=False),
                by_type=[
                    TypedIndicator(enabled=True, date_ranges={MONTH0}, type='caregiver'),
                    TypedIndicator(enabled=True, date_ranges={MONTH0}, type='beneficiary'),
                ]
            ),
            cases_active=ByTypeWithTotal(
                totals=BasicIndicator(enabled=False),
                by_type=[
                    TypedIndicator(enabled=True, date_ranges={MONTH0}, type='caregiver'),
                    TypedIndicator(enabled=True, date_ranges={MONTH0}, type='beneficiary'),
                ]
            )
        )

        self.assertEqual(set(get_indicator_slugs_from_config(config)), {
            'forms_submitted_month0',
            'cases_total_caregiver_month0',
            'cases_active_caregiver_month0',
            'cases_total_beneficiary_month0',
            'cases_active_beneficiary_month0'
        })
