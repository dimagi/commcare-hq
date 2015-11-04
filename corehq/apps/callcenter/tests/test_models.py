from corehq.apps.callcenter.const import WEEK1, WEEK0, MONTH0
from corehq.apps.callcenter.models import (
    TypedIndicator, ByTypeIndicator, CallCenterIndicatorConfig, BasicIndicator
)
from django.test import SimpleTestCase


class ModelTests(SimpleTestCase):
    def test_types_by_date_range(self):
        by_type = ByTypeIndicator(types=[
            TypedIndicator(active=True, date_ranges=[WEEK0, WEEK1], type='dog'),
            TypedIndicator(active=True, date_ranges=[WEEK0], type='cat'),
            TypedIndicator(active=True, date_ranges=[WEEK1], type='canary'),
            TypedIndicator(active=True, date_ranges=[WEEK1, MONTH0], type='fish'),
            TypedIndicator(active=False, date_ranges=[MONTH0], type='whale'),
        ])

        self.assertEqual(by_type.types_by_date_range(), {
            WEEK0: {'dog', 'cat'},
            WEEK1: {'dog', 'canary', 'fish'},
            MONTH0: {'fish'},
        })

    def _get_indicator_slugs(self, config, all_types=None):
        def basic_slugs(key, indicator_conf):
            for date_range in indicator_conf.date_ranges:
                yield '{}_{}'.format(key, date_range)

        def typed_slugs(key, types, indicator_conf):
            for date_range in indicator_conf.date_ranges:
                for type_ in types:
                    yield '{}_{}_{}'.format(key, type_, date_range)

        slugs = []
        if config.forms_submitted.active:
            slugs.extend(basic_slugs('forms_submitted', config.forms_submitted))

        for key in ['cases_total', 'cases_active', 'cases_opened', 'cases_closed']:
            indicator_config = getattr(config, key)
            if indicator_config.active:
                if indicator_config.total.active:
                    slugs.extend(basic_slugs(key, indicator_config.total))
                if indicator_config.all_types and all_types:
                    slugs.extend(typed_slugs(key, all_types, indicator_config))
                else:
                    for type_ in indicator_config.types:
                        if type_.active:
                            slugs.extend(typed_slugs(key, [type_.type], type_))

        return slugs

    def test_real_example(self):
        config = CallCenterIndicatorConfig(
            domain='domain',
            forms_submitted=BasicIndicator(active=True, include_legacy=False, date_ranges=[MONTH0]),
            cases_total=ByTypeIndicator(
                total=BasicIndicator(active=False),
                types=[
                    TypedIndicator(active=True, date_ranges=[MONTH0], type='caregiver'),
                    TypedIndicator(active=True, date_ranges=[MONTH0], type='beneficiary'),
                ]
            ),
            cases_active=ByTypeIndicator(
                total=BasicIndicator(active=False),
                types=[
                    TypedIndicator(active=True, date_ranges=[MONTH0], type='caregiver'),
                    TypedIndicator(active=True, date_ranges=[MONTH0], type='beneficiary'),
                ]
            )
        )

        self.assertEqual(set(self._get_indicator_slugs(config)), {
            'forms_submitted_month0',
            'cases_total_caregiver_month0',
            'cases_active_caregiver_month0',
            'cases_total_beneficiary_month0',
            'cases_active_beneficiary_month0'
        })
