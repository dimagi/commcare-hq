from datetime import datetime, timedelta
from dimagi.utils.rate_limit import rate_limit
from django.test import SimpleTestCase


class RateLimitTestCase(SimpleTestCase):
    def test_rate_limit(self):
        start = datetime.utcnow()
        rate_limit_count = 0
        iteration_count = 0

        while (datetime.utcnow() - start) < timedelta(seconds=18):
            # Only allow 10 actions every 5 seconds in an 18 second period of time
            if rate_limit('rate-limit-test', actions_allowed=10, how_often=5):
                rate_limit_count += 1
            iteration_count += 1

        self.assertEqual(rate_limit_count, 40)
        self.assertGreater(iteration_count, 40)
