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

    def accessed(self, identifier, **kwargs):
        """
        Handles recording the user's access.

        Does everything the ``CacheThrottle`` class does, plus logs the
        access within the database using the ``ApiAccess`` model.
        """
        # Do the import here, instead of top-level, so that the model is
        # only required when using this throttling mechanism.
        from tastypie.models import ApiAccess
        super(CacheDBThrottle, self).accessed(identifier, **kwargs)
        # Write out the access to the DB for logging purposes.
        url = kwargs.get('url', '')
        if len(url) > 255:
            url = url[:251] + '...'
        ApiAccess.objects.create(
            identifier=identifier,
            url=url,
            request_method=kwargs.get('request_method', '')
        )


class CustomResourceMeta(object):
    authorization = ReadOnlyAuthorization()
    authentication = LoginAndDomainAuthentication()
    serializer = CustomXMLSerializer()
    default_format = 'application/json'
    throttle = HQThrottle(
        throttle_at=getattr(settings, 'CCHQ_API_THROTTLE_REQUESTS', 25),
        timeframe=getattr(settings, 'CCHQ_API_THROTTLE_TIMEFRAME', 15)
    )
