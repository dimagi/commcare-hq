from __future__ import absolute_import
from __future__ import unicode_literals
import collections
import random

from memoized import memoized

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


NEW_USER_NUMBER_OPTION_SHOW_NUM = 'show_number'
NEW_USER_NUMBER_OPTION_HIDE_NUM = 'hide_number'


NEW_USER_NUMBER = ABTestConfig(
    'New User Phone Number',
    'new_phone_jan2016',
    (NEW_USER_NUMBER_OPTION_SHOW_NUM, NEW_USER_NUMBER_OPTION_HIDE_NUM)
)


DATA_FEEDBACK_LOOP_OPTION_ON = 'data_feedback_loop_on'
DATA_FEEDBACK_LOOP_OPTION_OFF = 'data_feedback_loop_off'


DATA_FEEDBACK_LOOP = ABTestConfig(
    'Data Feedback Loop',
    'data_feedback_loop_feb2018',
    (DATA_FEEDBACK_LOOP_OPTION_ON, DATA_FEEDBACK_LOOP_OPTION_OFF)
)
