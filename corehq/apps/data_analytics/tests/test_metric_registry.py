import json
from datetime import datetime
from unittest.mock import MagicMock

from django.db.models import BooleanField, DateTimeField, IntegerField
from django.test import SimpleTestCase

from corehq.apps.domain.calculations import all_domain_stats
from corehq.apps.domain.tests.test_domain_calculated_properties import (
    BaseCalculatedPropertiesTest,
)

from ..feature_calcs import FEATURE_METRICS
from ..metric_registry import (
    DomainContext,
    MetricDef,
    collect_daily_metrics_for_domain,
    collect_metrics_for_domain,
    get_metrics_by_schedule,
    get_metrics_registry,
)
from ..models import DOMAIN_METRICS_TO_PROPERTIES_MAP, DomainMetrics


class TestMetricDef(SimpleTestCase):

    def test_metric_def_boolean_defaults(self):
        metric = MetricDef(
            field_name='has_feature',
            cp_name='cp_has_feature',
            calc_fn=lambda ctx: True,
        )
        assert metric.is_boolean is True
        assert metric.schedule == 'monthly'

    def test_metric_def_count(self):
        metric = MetricDef(
            field_name='widget_count',
            cp_name='cp_n_widgets',
            calc_fn=lambda ctx: 5,
            is_boolean=False,
        )
        assert metric.is_boolean is False

    def test_get_metrics_by_schedule_filters(self):
        daily = MetricDef('a', 'cp_a', lambda ctx: 1,
                          is_boolean=False, schedule='daily')
        monthly = MetricDef('b', 'cp_b', lambda ctx: True,
                            schedule='monthly')
        metrics = [daily, monthly]
        assert get_metrics_by_schedule(metrics, 'daily') == [daily]
        assert get_metrics_by_schedule(metrics, 'monthly') == [monthly]


class TestDomainContext(SimpleTestCase):

    def test_apps_cached(self):
        domain_obj = MagicMock()
        domain_obj.name = 'test-domain'
        app1, app2 = MagicMock(), MagicMock()
        app1.is_remote_app.return_value = False
        app2.is_remote_app.return_value = False
        domain_obj.full_applications.return_value = [app1, app2]
        ctx = DomainContext(domain_obj)
        _ = ctx.apps
        _ = ctx.apps  # second access
        domain_obj.full_applications.assert_called_once()

    def test_excludes_remote_apps(self):
        domain_obj = MagicMock()
        domain_obj.name = 'test-domain'
        remote_app = MagicMock()
        remote_app.is_remote_app.return_value = True
        local_app = MagicMock()
        local_app.is_remote_app.return_value = False
        domain_obj.full_applications.return_value = [remote_app, local_app]
        ctx = DomainContext(domain_obj)
        assert ctx.apps == [local_app]

    def test_domain_name(self):
        domain_obj = MagicMock()
        domain_obj.name = 'my-domain'
        ctx = DomainContext(domain_obj)
        assert ctx.domain == 'my-domain'


class TestCollectMetricsForDomain(SimpleTestCase):

    def test_skips_boolean_already_true(self):
        called = []

        def calc_fn(ctx):
            called.append(True)
            return True

        metric = MetricDef('has_feature', 'cp_has_feature', calc_fn)

        existing = MagicMock()
        existing.has_feature = True

        domain_obj = MagicMock()
        domain_obj.name = 'test'

        updates = collect_metrics_for_domain(domain_obj, [metric], existing)
        assert updates == {}
        assert called == []

    def test_computes_boolean_when_false(self):
        metric = MetricDef(
            'has_feature', 'cp_has_feature', lambda ctx: True
        )

        existing = MagicMock()
        existing.has_feature = False

        domain_obj = MagicMock()
        domain_obj.name = 'test'

        updates = collect_metrics_for_domain(domain_obj, [metric], existing)
        assert updates == {'has_feature': True}

    def test_computes_boolean_when_none(self):
        metric = MetricDef(
            'has_feature', 'cp_has_feature', lambda ctx: False
        )

        existing = MagicMock()
        existing.has_feature = None

        domain_obj = MagicMock()
        domain_obj.name = 'test'

        updates = collect_metrics_for_domain(domain_obj, [metric], existing)
        assert updates == {'has_feature': False}

    def test_always_computes_count(self):
        metric = MetricDef(
            'widget_count', 'cp_n_widgets', lambda ctx: 42,
            is_boolean=False,
        )

        existing = MagicMock()
        existing.widget_count = 42

        domain_obj = MagicMock()
        domain_obj.name = 'test'

        updates = collect_metrics_for_domain(domain_obj, [metric], existing)
        assert updates == {'widget_count': 42}

    def test_handles_no_existing_metrics(self):
        metric = MetricDef(
            'has_feature', 'cp_has_feature', lambda ctx: True
        )

        domain_obj = MagicMock()
        domain_obj.name = 'test'

        updates = collect_metrics_for_domain(
            domain_obj, [metric], existing_metrics=None
        )
        assert updates == {'has_feature': True}

    def test_logs_and_skips_on_calc_error(self):
        def bad_calc(ctx):
            raise ValueError("boom")

        good_metric = MetricDef(
            'count', 'cp_n_count', lambda ctx: 5, is_boolean=False
        )
        bad_metric = MetricDef(
            'has_bad', 'cp_has_bad', bad_calc
        )

        domain_obj = MagicMock()
        domain_obj.name = 'test'

        updates = collect_metrics_for_domain(
            domain_obj, [bad_metric, good_metric], existing_metrics=None
        )
        assert updates == {'count': 5}


class TestDomainAPIExposesFeatureMetrics(SimpleTestCase):
    """Verify that FEATURE_METRICS are reachable through the Domain API.

    The Domain API exposes calculated properties by calling
    DomainMetrics.to_calculated_properties(), which uses
    DOMAIN_METRICS_TO_PROPERTIES_MAP to produce cp_-prefixed keys.
    """

    def test_feature_metrics_in_domain_metrics_to_properties_map(self):
        """Every FEATURE_METRICS entry must be in DOMAIN_METRICS_TO_PROPERTIES_MAP."""
        for metric in FEATURE_METRICS:
            self.assertIn(
                metric.field_name,
                DOMAIN_METRICS_TO_PROPERTIES_MAP,
                msg=f'{metric.field_name!r} missing from DOMAIN_METRICS_TO_PROPERTIES_MAP',
            )
            self.assertEqual(
                DOMAIN_METRICS_TO_PROPERTIES_MAP[metric.field_name],
                metric.cp_name,
                msg=f'{metric.field_name!r}: expected {metric.cp_name!r}',
            )

    def test_feature_metrics_returned_by_to_calculated_properties(self):
        """to_calculated_properties() must include all FEATURE_METRICS cp_names.

        This method is exactly what DomainMetadataResource calls to populate
        the 'calculated_properties' field of the Domain API response.
        """
        # Build an in-memory DomainMetrics with all required fields set to
        # sensible defaults (mirrors the helper in test_tasks.py).
        kwargs = {}
        for field in DomainMetrics._meta.get_fields():
            if isinstance(field, BooleanField) and not field.null:
                kwargs[field.name] = False
            elif isinstance(field, DateTimeField) and not field.null:
                kwargs[field.name] = datetime(2024, 1, 1)
            elif isinstance(field, IntegerField) and not field.null:
                kwargs[field.name] = 0
        # Set feature metrics to known values
        for metric in FEATURE_METRICS:
            kwargs[metric.field_name] = True if metric.is_boolean else 1

        metrics = DomainMetrics(domain='test-domain', **kwargs)
        result = metrics.to_calculated_properties()

        for metric in FEATURE_METRICS:
            self.assertIn(
                metric.cp_name,
                result,
                msg=f'{metric.cp_name!r} missing from to_calculated_properties()',
            )
            expected = True if metric.is_boolean else 1
            self.assertEqual(
                result[metric.cp_name],
                expected,
                msg=f'{metric.cp_name!r}: expected {expected!r}, got {result[metric.cp_name]!r}',
            )


class TestRegistryCoversMap(SimpleTestCase):

    def test_registry_covers_all_salesforce_mappings(self):
        """The registry must produce the same Salesforce mappings
        as DOMAIN_METRICS_TO_PROPERTIES_MAP."""
        generated = {m.field_name: m.cp_name for m in get_metrics_registry()}
        for field, cp_name in DOMAIN_METRICS_TO_PROPERTIES_MAP.items():
            assert field in generated, (
                f'{field} missing from metrics registry'
            )
            assert generated[field] == cp_name, (
                f'{field}: expected {cp_name}, got {generated[field]}'
            )

    def test_no_duplicate_field_names(self):
        field_names = [m.field_name for m in get_metrics_registry()]
        assert len(field_names) == len(set(field_names)), (
            f'Duplicate field names: '
            f'{[n for n in field_names if field_names.count(n) > 1]}'
        )


class DomainCalculatedPropertiesTest(BaseCalculatedPropertiesTest):

    def test_calculated_properties_are_serializable(self):
        stats = all_domain_stats()
        metrics = collect_daily_metrics_for_domain(self.domain, stats)
        json.dumps(metrics)

    def test_domain_does_not_have_project_icon(self):
        stats = all_domain_stats()
        metrics = collect_daily_metrics_for_domain(self.domain, stats)
        self.assertFalse(metrics['has_project_icon'])
