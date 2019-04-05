from __future__ import absolute_import
from __future__ import unicode_literals
import random
import logging
from django.core.cache import cache

from memoized import memoized


logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


class SessionAbTestConfig(object):

    def __init__(self, name, slug, options, is_debug=False, force_refresh=False):
        """
        :param name: (string) The name passed to the analytics API
        :param slug: (string) a unique slug, preferably with a date
            (my_test_dec2018). Used only in generating the cookie and cache IDs.
        :param options: (tuple) a tuple of option values

        Optional for DEV USE ONLY:
        :param is_debug: (boolean) whether debug (logging) mode is active
        :param force_refresh: (boolean) whether to force a refresh of the values
        """
        self.name = name
        self.slug = slug
        self.options = options
        self.is_debug = is_debug
        self.force_refresh = force_refresh


class SessionAbTest(object):
    """
    Initialize a user session A/B test from a SessionABTestConfig.
    This type of A/B test is useful for anonymous users (pre login),
    and uses the users's unique session id and cookies to maintain consistency.
    """

    def __init__(self, config, request):
        """
        :param config: an instance of SessionABTestConfig
        :param request: view request
        """
        self.config = config
        self.request = request

        # If the session isn't manually saved, then incognito will cause the
        # session_key to return None, making caching unique values per user not
        # possible.
        if not self.request.session.session_key:
            self.request.session.save()

    @property
    def _cookie_id(self):
        return "{}_ab".format(self.config.slug)

    @property
    def _cache_id(self):
        return "{}_{}".format(self._cookie_id, self.request.session.session_key)

    @memoized
    def version(self, assign_if_blank=True):
        value = None
        if cache.get(self._cache_id):
            value = cache.get(self._cache_id)
            self._debug_message("fetched version from cache '{}'".format(value))
        elif (self._cookie_id in self.request.COOKIES
              and not self.config.force_refresh):
            value = self.request.COOKIES[self._cookie_id]
            self._debug_message("fetched version from cookie '{}'".format(value))
        elif assign_if_blank:
            value = random.choice(self.config.options)
            self._debug_message("fetched new version '{}'".format(value))
        self.cache_version(value)
        return value

    def cache_version(self, version):
        self._debug_message("cache version '{}' under '{}'".format(
            version, self._cache_id))
        cache.set(self._cache_id, version)
        # fyi default cache timeout is 300 sec (5 min)

    def _clear_cache(self):
        self._debug_message("clearing cache '{}'".format(self._cache_id))
        cache.delete(self._cache_id)

    def _debug_message(self, message):
        if self.config.is_debug:
            logger.info("SESSION AB TEST [{}]: {}".format(self._cookie_id, message))

    def update_response(self, response):
        if self.config.force_refresh:
            self._clear_response(response)
        version = self.version()
        self._debug_message("storing cookie value '{}' in '{}'".format(
            version, self._cookie_id))
        response.set_cookie(self._cookie_id, version)

    def _clear_response(self, response):
        self._debug_message("clearing cookies '{}'".format(self._cookie_id))
        response.delete_cookie(self._cookie_id)

    @property
    def context(self):
        """
        Assign this to a variable in your template context.

        USAGE IN TEMPLATE:
        {% analytics_ab_test '<api>.<slug>' <context_variable> %}

        <api> - the api name (e.g. kissmetrics)
        <slug> - is a unique slug (can be different from the slug in AbTestConfig
        <context_variable> - the context variable you assign this property to

        kissmetrics is already set up to auto detect analytics_ab_test tags and
        send the results on page load. Please do not manually do this!

        :return: dict
        """
        if self.config.force_refresh:
            self._clear_cache()
        context = {
            'name': self.config.name,
            'version': self.version(),
        }
        self._debug_message("Fetching Template Context {}".format(context))
        return context


APPCUES_TEMPLATE_APP_VARIANT_A = 'Variant A'
APPCUES_TEMPLATE_APP_VARIANT_B = 'Variant B'

APPCUES_V3_APP = SessionAbTestConfig(
    'Appcues Template App',
    'appcues_template_app_december2018',
    (APPCUES_TEMPLATE_APP_VARIANT_A, APPCUES_TEMPLATE_APP_VARIANT_B)
)


DEMO_WORKFLOW_V2_CONTROL = 'control'
DEMO_WORKFLOW_V2_VARIANT = 'variant'

DEMO_WORKFLOW_V2 = SessionAbTestConfig(
    'Demo Workflow A/B V2',
    'demo_workflow_mar2019',
    (DEMO_WORKFLOW_V2_CONTROL, DEMO_WORKFLOW_V2_VARIANT)
)
