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
            return random.sample(self.options, 1)[0]
        return None

    def update_response(self, response):
        response.set_cookie(self._cookie_id, self.version())

    @property
    def context(self):
        return {
            'name': self.name,
            'version': self.version(),
        }


NEW_USER_NUMBER_OPTION_SHOW_NUM = 'show_number'
NEW_USER_NUMBER_OPTION_HIDE_NUM = 'hide_number'


NEW_USER_NUMBER = ABTestConfig(
    'New User Phone Number',
    'new_phone_may2018',
    (NEW_USER_NUMBER_OPTION_SHOW_NUM, NEW_USER_NUMBER_OPTION_HIDE_NUM)
)


APPCUES_TEMPLATE_APP_OPTION_ON = 'appcues_on'
APPCUES_TEMPLATE_APP_OPTION_OFF = 'appcues_off'


APPCUES_TEMPLATE_APP = ABTestConfig(
    'Appcues Template App',
    'appcues_template_app_june2018',
    (APPCUES_TEMPLATE_APP_OPTION_ON, APPCUES_TEMPLATE_APP_OPTION_OFF)
)


@memoized
def appcues_template_app_test(request):
    # See if user is in test
    test = ABTest(APPCUES_TEMPLATE_APP, request)
    if test.version(assign_if_blank=False) != APPCUES_TEMPLATE_APP_OPTION_ON:
        return False

    # If the user's trial has run out, they may no longer have access to web apps
    domain = getattr(request, 'domain', None)
    if domain:
        subscription = Subscription.get_active_subscription_by_domain(domain)
        if not subscription or not subscription.is_trial:
            return False

    return True
