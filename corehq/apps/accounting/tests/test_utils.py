from datetime import date

from django.test import SimpleTestCase, TestCase

import pytest

from corehq.apps.accounting.models import SoftwarePlanEdition, Subscription
from corehq.apps.accounting.tests.utils import DomainSubscriptionMixin
from corehq.apps.accounting.utils import (
    clear_plan_version_cache,
    is_date_range_overlapping,
)
from corehq.apps.accounting.utils.software_plans import plan_enabled
from corehq.apps.domain.shortcuts import create_domain


class TestIsDateRangeOverlapping(SimpleTestCase):
    def test_first_range_is_contained_in_second_range(self):
        assert is_date_range_overlapping(date(2025, 1, 3), date(2025, 1, 6),
                                         date(2025, 1, 1), date(2025, 1, 10))

    def test_second_range_is_contained_in_first_range(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 5), date(2025, 1, 7))

    def test_partial_overlap_start(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2024, 12, 20), date(2025, 1, 2))

    def test_partial_overlap_end(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 9), date(2025, 1, 20))

    def test_exact_overlap(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 1), date(2025, 1, 10))

    def test_no_overlap_before(self):
        assert not is_date_range_overlapping(date(2025, 1, 10), date(2025, 1, 20),
                                             date(2025, 1, 1), date(2025, 1, 9))

    def test_no_overlap_after(self):
        assert not is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 9),
                                             date(2025, 1, 10), date(2025, 1, 20))

    def test_adjacent_ranges_do_not_overlap(self):
        # Two ranges that touch at a boundary is not considered an overlap.
        # This is a special case for our accounting system
        assert not is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                             date(2025, 1, 10), date(2025, 1, 20))

        assert not is_date_range_overlapping(date(2025, 1, 10), date(2025, 1, 20),
                                             date(2025, 1, 1), date(2025, 1, 10))

    def test_same_start_date_is_overlap(self):
        assert is_date_range_overlapping(date(2025, 1, 5), date(2025, 1, 10),
                                         date(2025, 1, 5), date(2025, 1, 15))

    def test_same_end_date_is_overlap(self):
        assert is_date_range_overlapping(date(2025, 1, 1), date(2025, 1, 10),
                                         date(2025, 1, 5), date(2025, 1, 10))

    def test_first_range_infinite_end(self):
        assert is_date_range_overlapping(date(2025, 1, 1), None,
                                         date(2025, 1, 10), date(2025, 1, 20))

    def test_second_range_infinite_end(self):
        assert is_date_range_overlapping(date(2025, 1, 10), date(2025, 1, 20),
                                         date(2025, 1, 1), None)

    def test_both_ranges_infinite_end(self):
        assert is_date_range_overlapping(date(2025, 1, 1), None,
                                         date(2025, 2, 1), None)

    def test_first_range_infinite_end_but_start_after_second_range_end(self):
        assert not is_date_range_overlapping(date(2025, 1, 1), None,
                                             date(2024, 1, 1), date(2024, 12, 31))

    def test_second_range_infinite_end_but_start_after_first_range_end(self):
        assert not is_date_range_overlapping(date(2024, 1, 1), date(2024, 12, 31),
                                             date(2025, 1, 1), None)


class TestPlanEnabled(TestCase, DomainSubscriptionMixin):
    domain = 'test-plan-enabled'

    def setUp(self):
        self.domain_obj = create_domain(self.domain)
        self.addCleanup(self.domain_obj.delete)
        self.addCleanup(clear_plan_version_cache)
        self.addCleanup(Subscription.clear_caches, self.domain)

    def test_std_pro_enabled(self):
        self.setup_subscription(self.domain, SoftwarePlanEdition.STANDARD)
        assert plan_enabled(SoftwarePlanEdition.PRO, self.domain) is False

    def test_pro_pro_enabled(self):
        self.setup_subscription(self.domain, SoftwarePlanEdition.PRO)
        assert plan_enabled(SoftwarePlanEdition.PRO, self.domain) is True

    def test_adv_pro_enabled(self):
        self.setup_subscription(self.domain, SoftwarePlanEdition.ADVANCED)
        assert plan_enabled(SoftwarePlanEdition.PRO, self.domain) is True

    def test_pro_std_enabled(self):
        self.setup_subscription(self.domain, SoftwarePlanEdition.PRO)
        assert plan_enabled(SoftwarePlanEdition.STANDARD, self.domain) is True

    def test_pro_adv_enabled(self):
        self.setup_subscription(self.domain, SoftwarePlanEdition.PRO)
        assert plan_enabled(SoftwarePlanEdition.ADVANCED, self.domain) is False

    def test_no_plan(self):
        self.setup_subscription(self.domain, SoftwarePlanEdition.PRO)
        with pytest.raises(AssertionError):
            plan_enabled("AIN'T GOT NO PLAN", self.domain)

    def test_no_subs(self):
        assert Subscription.get_active_subscription_by_domain(self.domain) is None
        assert plan_enabled(SoftwarePlanEdition.PRO, self.domain) is False
