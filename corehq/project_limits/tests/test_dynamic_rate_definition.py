from django.test import TestCase

from corehq.project_limits.models import DynamicRateDefinition
from corehq.project_limits.rate_limiter import get_dynamic_rate_definition, \
    rate_definition_from_db_object, RateDefinition
from corehq.project_limits.shortcuts import get_standard_ratio_rate_definition


class DynamicRateDefinitionTest(TestCase):
    @classmethod
    def setUpClass(cls):
        for dynamic_rate_definition in DynamicRateDefinition.objects.all():
            # delete one by one to also trigger clearing caches
            dynamic_rate_definition.delete()
        super().setUpClass()

    def test_get_dynamic_rate_definition(self):
        self.addCleanup(lambda: DynamicRateDefinition.objects.get(key='test').delete())

        # On the first call, the return value is the default given
        self.assertEqual(
            get_dynamic_rate_definition(
                'test', default=get_standard_ratio_rate_definition(events_per_day=50)),
            get_standard_ratio_rate_definition(events_per_day=50)
        )
        # once it's created changing the default doesn't affect the return value
        self.assertEqual(
            get_dynamic_rate_definition(
                'test', default=get_standard_ratio_rate_definition(events_per_day=1000)),
            get_standard_ratio_rate_definition(events_per_day=50)
        )
        # The following lines simulates editing through the Django Admin
        dynamic_rate_definition = DynamicRateDefinition.objects.get(key='test')
        dynamic_rate_definition.per_week = 64
        dynamic_rate_definition.per_day = 32
        dynamic_rate_definition.per_hour = 16
        dynamic_rate_definition.per_minute = 8
        dynamic_rate_definition.per_second = 4
        dynamic_rate_definition.save()
        # After editing, the return value is the newly saved value
        # (and the default doesn't matter)
        self.assertEqual(
            get_dynamic_rate_definition(
                'test', default=get_standard_ratio_rate_definition(events_per_day=50)),
            rate_definition_from_db_object(dynamic_rate_definition)
        )
        # Deleting the db object makes it take on the given default value again
        dynamic_rate_definition.delete()
        self.assertEqual(
            get_dynamic_rate_definition(
                'test', default=get_standard_ratio_rate_definition(events_per_day=95)),
            get_standard_ratio_rate_definition(events_per_day=95)
        )

    def test_conversion(self):
        self.assertEqual(
            rate_definition_from_db_object(DynamicRateDefinition(
                key='a',
                per_week=10,
            )),
            RateDefinition(
                per_week=10
            )
        )
        self.assertEqual(
            rate_definition_from_db_object(DynamicRateDefinition(
                key='a',
                per_week=10,
                per_day=8.5,
                per_hour=7,
                per_minute=5.5,
                per_second=4,
            )),
            RateDefinition(
                per_week=10,
                per_day=8.5,
                per_hour=7,
                per_minute=5.5,
                per_second=4,
            )
        )
