from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import division

from corehq.project_limits.rate_limiter import RateLimiter


def test_create_rate_limiter():
    """
    Just test that very basic usage at least doesn't error
    """
    MyFeatureRateLimiter = RateLimiter.create('my_feature')
    my_feature_rate_limiter = MyFeatureRateLimiter(per_week=50000, per_day=13000, per_second=5)
    if my_feature_rate_limiter.allow_usage('my_domain'):
        my_feature_rate_limiter.report_usage('my_domain')
