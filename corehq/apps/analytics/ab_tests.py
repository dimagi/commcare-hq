import collections
import random

from dimagi.utils.decorators.memoized import memoized

ABTestConfig = collections.namedtuple('ABTestConfig', ('name', 'slug', 'options'))


class ABTest(object):
    """
    Initialize A/B test with an ABTestConfig.
    """

    def __init__(self, config, request):
        self.name = config.name
        self.slug = config.slug
        self.options = config.options
        self.request = request

    @property
    def _cookie_id(self):
        return "{}_ab".format(self.slug)

    @property
    @memoized
    def version(self):
        if self._cookie_id not in self.request.COOKIES:
            version = random.sample(self.options, 1)[0]  # todo weighted options
        else:
            version = self.request.COOKIES[self._cookie_id]
        return version

    def update_response(self, response):
        response.set_cookie(self._cookie_id, self.version)

    @property
    def context(self):
        return {
            'name': self.name,
            'version': self.version,
        }
