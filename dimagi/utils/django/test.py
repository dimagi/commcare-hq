from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import (NoSuchElementException,
    ElementNotVisibleException)
from django.test import TestCase
from django.conf import settings
from functools import wraps
import time

class SeleniumWrapper(object):
    """
    Unlike after page loads, selenium doesn't wait for events to finish
    firing after interactions with the page.  This can make test code quite
    verbose, with many explicit waits after clicks.

    This class wraps calls to webdriver methods in a try-except block that
    catches NoSuchElementExceptions and provides the ability to wait and retry
    the same methods.  This behavior can be determined using keyword arguments
    to the webdriver methods:

        duration -- seconds to wait for success before rethrowing (default: 10)
        interval -- seconds between retries (default: min(.5, duration))
        ensure_displayed -- retry if element is not visible (default: True)

    """

    def __init__(self, browser_name, base_url, *args, **kwargs):
        self.base_url = base_url
        self.browser_name = browser_name.capitalize()
        self.driver = getattr(webdriver, self.browser_name)(*args, **kwargs)

    def get(self, path):
        return self.driver.get(self.base_url + path)

    def wait_until(self, fn, time=10):
        # todo: allow wrapper usage within function
        return WebDriverWait(self.driver, time).until(fn)

    def wait_until_not(self, fn, time=10):
        return WebDriverWait(self.driver, time).until_not(fn)

    def sleep(self, duration):
        return time.sleep(duration)

    def __getattr__(self, name):
        val = getattr(self.driver, name)

        if not hasattr(val, '__call__'):
            return val

        return self._wrap_driver_attr_access(val)

    def _wrap_driver_attr_access(self, attr):

        @wraps(attr)
        def wrapped(*args, **kwargs):
            if 'interval' in kwargs and 'duration' not in kwargs:
                raise Exception("Invalid wrapped webdriver method call")

            duration = kwargs.pop('duration', 10)
            interval = kwargs.pop('interval', min(.5, duration))
            ensure_displayed = kwargs.pop('ensure_displayed', True)

            while True:
                try:
                    retval = attr(*args, **kwargs)

                    if isinstance(retval, WebElement) and ensure_displayed \
                       and not retval.is_displayed():
                        raise ElementNotVisibleException()

                    return retval
                except (NoSuchElementException, ElementNotVisibleException):
                    if duration < 0.00000001:
                        raise
                    else:
                        time.sleep(interval)
                        duration -= interval

        return wrapped


class SeleniumTestCase(TestCase):
    """
    A test class that sets up a WebDriver and lets you access webdriver
    attributes directly on the class.

    """

    base_url = ''

    def __getattr__(self, name):
        return getattr(self.driver, name)

    @classmethod
    def setUpClass(cls):
        kwargs = {
            'browser_name': settings.SELENIUM_BROWSER,
            'base_url': cls.base_url
        }

        if settings.SELENIUM_REMOTE_URL:
            kwargs.update({
                'browser_name': 'Remote',
                'command_executor': settings.SELENIUM_REMOTE_URL,
                'desired_capabilities': getattr(DesiredCapabilities,
                                                settings.SELENIUM_BROWSER.upper())
            })

        cls.driver = SeleniumWrapper(**kwargs)

        super(SeleniumTestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(SeleniumTestCase, cls).tearDownClass()
        cls.driver.quit()
