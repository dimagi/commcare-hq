from django.conf import settings
from tastypie.authorization import ReadOnlyAuthorization
from tastypie.throttle import CacheDBThrottle

from corehq.apps.api.resources.auth import LoginAndDomainAuthentication
from corehq.apps.api.serializers import CustomXMLSerializer
from corehq.toggles import API_THROTTLE_WHITELIST


class HQThrottle(CacheDBThrottle):

    def should_be_throttled(self, identifier, **kwargs):
        if API_THROTTLE_WHITELIST.enabled(identifier):
            return False

        return super(HQThrottle, self).should_be_throttled(identifier, **kwargs)


class CustomResourceMeta(object):
    authorization = ReadOnlyAuthorization()
    authentication = LoginAndDomainAuthentication()
    serializer = CustomXMLSerializer()
    default_format = 'application/json'
    throttle = HQThrottle(
        throttle_at=getattr(settings, 'CCHQ_API_THROTTLE_REQUESTS', 25),
        timeframe=getattr(settings, 'CCHQ_API_THROTTLE_TIMEFRAME', 15)
    )
