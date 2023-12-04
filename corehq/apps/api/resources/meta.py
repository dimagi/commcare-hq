from django.conf import settings

from tastypie.authorization import ReadOnlyAuthorization
from tastypie.throttle import BaseThrottle

from corehq.apps.api.resources.auth import AdminAuthentication, LoginAndDomainAuthentication
from corehq.apps.api.serializers import CustomXMLSerializer
from corehq.project_limits.rate_limiter import (
    PerUserRateDefinition,
    RateDefinition,
    RateLimiter,
)
from corehq.project_limits.shortcuts import get_standard_ratio_rate_definition
from corehq.toggles import API_THROTTLE_WHITELIST


api_rate_limiter = RateLimiter(
    feature_key='api',
    get_rate_limits=PerUserRateDefinition(
        per_user_rate_definition=get_standard_ratio_rate_definition(events_per_day=1000),
        constant_rate_definition=RateDefinition(
            per_week=100,
            per_day=50,
            per_hour=30,
            per_minute=10,
            per_second=1,
        ),
    ).get_rate_limits
)


def get_hq_throttle():
    return HQThrottle(
        throttle_at=getattr(settings, 'CCHQ_API_THROTTLE_REQUESTS', 25),
        timeframe=getattr(settings, 'CCHQ_API_THROTTLE_TIMEFRAME', 15)
    )


class HQThrottle(BaseThrottle):

    def should_be_throttled(self, identifier, **kwargs):
        if API_THROTTLE_WHITELIST.enabled(identifier.username):
            return False

        return not api_rate_limiter.allow_usage(identifier.domain)

    def retry_after(self, identifier):
        return api_rate_limiter.get_retry_after(scope=identifier.domain)

    def accessed(self, identifier, **kwargs):
        """
        Handles recording the user's access.

        Does everything the ``CacheThrottle`` class does, plus logs the
        access within the database using the ``ApiAccess`` model.
        """
        # Do the import here, instead of top-level, so that the model is
        # only required when using this throttling mechanism.
        from tastypie.models import ApiAccess

        api_rate_limiter.report_usage(identifier.domain)
        # Write out the access to the DB for logging purposes.
        url = kwargs.get('url', '')
        if len(url) > 255:
            url = url[:251] + '...'
        ApiAccess.objects.create(
            identifier=identifier.username,
            url=url,
            request_method=kwargs.get('request_method', '')
        )


class CustomResourceMeta(object):
    authorization = ReadOnlyAuthorization()
    authentication = LoginAndDomainAuthentication()
    serializer = CustomXMLSerializer()
    default_format = 'application/json'
    throttle = get_hq_throttle()


class AdminResourceMeta(CustomResourceMeta):
    authentication = AdminAuthentication()
    throttle = BaseThrottle()
