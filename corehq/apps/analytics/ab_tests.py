from __future__ import absolute_import
from __future__ import unicode_literals
import collections
import random

from memoized import memoized
from corehq.apps.accounting.models import Subscription

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

    @memoized
    def version(self, assign_if_blank=True):
        if self._cookie_id in self.request.COOKIES:
            return self.request.COOKIES[self._cookie_id]
        if assign_if_blank:
            return random.choice(self.options)
        return None

    def update_response(self, response):
        response.set_cookie(self._cookie_id, self.version())

    @property
    def context(self):
        return {
            'name': self.name,
            'version': self.version(),
        }


DEMO_CTA_OPTION_ON = 'demo_on'
DEMO_CTA_OPTION_OFF = 'demo_off'

DEMO_CTA = ABTestConfig(
    'Demo CTA on Signup',
    'demo_cta_aug2018',
    (DEMO_CTA_OPTION_ON, DEMO_CTA_OPTION_OFF)
)



@memoized
def appcues_template_app_test(request):
    # If the user's trial has run out, they may no longer have access to web apps
    domain = getattr(request, 'domain', None)
    if domain:
        subscription = Subscription.get_active_subscription_by_domain(domain)
        if not subscription or not subscription.is_trial:
            return False

    return True
