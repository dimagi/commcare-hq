from tastypie.throttle import CacheThrottle

from corehq.toggles import API_THROTTLE_WHITELIST


class HQThrottle(CacheThrottle):

    def should_be_throttled(self, identifier, **kwargs):
        if API_THROTTLE_WHITELIST.enabled(identifier):
            return False

        return super(HQThrottle, self).should_be_throttled(identifier, **kwargs)
