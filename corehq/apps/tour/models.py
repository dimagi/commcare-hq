import collections
from django.core import cache


GuidedTourStep = collections.namedtuple('GuidedTourStep', ['element', 'title', 'content'])


class StaticGuidedTour(object):

    def __init__(self, slug, steps):
        self.slug = slug
        if not isinstance(steps, list):
            raise ValueError("steps should be a list of GuidedTourStep")
        self.steps = steps

    def get_tour_data(self):
        return {
            'steps': map(lambda s: dict(s._asdict()), self.steps),
        }

    def _get_cache_key(self, request, domain):
        return "{}.{}.{}".format(domain, request.couch_user.username, self.slug)

    @property
    def cache_location(self):
        return cache.caches['default']

    def setup(self, request, domain):
        cache_key = self._get_cache_key(request, domain)
        self.cache_location.set(cache_key, 'start')

    def clear_cache(self, request, domain):
        cache_key = self._get_cache_key(request, domain)
        self.cache_location.delete(cache_key)

    def is_tour_available(self, request, domain):
        cache_key = self._get_cache_key(request, domain)
        return self.cache_location.has_key(cache_key)



