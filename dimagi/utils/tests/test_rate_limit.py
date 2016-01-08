from dimagi.utils.rate_limit import rate_limit, DomainRateLimiter
from django.test import SimpleTestCase
# import the datetime module and not datetime.datetime:
# "datetime" has to be the datetime module since the tests/__init__.py file
# just imports * from all test files and the json_format_datetime doctest
# expects datetime to be the datetime module
import datetime


class RateLimitTestCase(SimpleTestCase):
    def test_rate_limit(self):
        start = datetime.datetime.utcnow()
        rate_limit_count = 0
        iteration_count = 0

        while (datetime.datetime.utcnow() - start) < datetime.timedelta(seconds=5):
            # Only allow 10 actions every 3 seconds in an 5 second period of time
            if rate_limit('rate-limit-test', actions_allowed=10, how_often=3):
                rate_limit_count += 1
            iteration_count += 1

        self.assertEqual(rate_limit_count, 20)
        self.assertGreater(iteration_count, 20)

    def test_domain_rate_limit(self):
        rate_limiter = DomainRateLimiter('rate-limit-domain-', 10, 3)
        domains = ('d1', 'd2')
        domain_counts = {domain: 0 for domain in domains}

        start = datetime.datetime.utcnow()
        iteration_count = 0

        while (datetime.datetime.utcnow() - start) < datetime.timedelta(seconds=5):
            # Only allow 10 actions every 3 seconds in an 5 second period of time
            for domain in domains:
                if rate_limiter.can_perform_action(domain):
                    domain_counts[domain] += 1
            iteration_count += 1

        for domain in domains:
            self.assertEqual(domain_counts[domain], 20)
        self.assertGreater(iteration_count, 20)
