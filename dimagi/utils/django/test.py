from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import (NoSuchElementException,
    ElementNotVisibleException)
from django.test import TestCase
from django.conf import settings
from functools import wraps
import time


class SeleniumTestCase(TestCase):
    """
    A test class that sets up a WebDriver and lets you access webdriver
    attributes directly on the class.

    Unlike after page loads, selenium doesn't wait for events to finish
    firing after interactions with the page.  This can make test code quite
    verbose, with many explicit waits after clicks.

    This class wraps calls to webdriver methods in a try-except block that
    catches NoSuchElementExceptions and provides the ability to wait and retry
    the same methods.  This behavior can be determined using keyword arguments
    to the webdriver methods:

        retry -- boolean (default: True) - whether to retry
        duration -- seconds to wait for success before rethrowing (default: 10)
        interval -- seconds between retries (default: min(.5, duration))
        ensure_displayed -- retry if element is not visible (default: True)

    """

    base_url = ''

    @classmethod
    def setUpClass(cls):
        super(SeleniumTestCase, cls).setUpClass()
        cls.driver = getattr(webdriver, settings.SELENIUM_DRIVER)()

    @classmethod
    def tearDownClass(cls):
        super(SeleniumTestCase, cls).tearDownClass()
        cls.driver.quit()

    @classmethod
    def get(cls, path):
        return cls.driver.get(cls.base_url + path)

    @classmethod
    def wait_until(cls, fn, time=10):
        # todo: allow wrapper usage within function
        return WebDriverWait(cls.driver, time).until(fn)

    @classmethod
    def wait_until_not(cls, fn, time=10):
        return WebDriverWait(cls.driver, time).until_not(fn)

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

            retry = kwargs.pop('retry', True)
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
                    if duration < 0.00000001 or not retry:
                        raise
                    else:
                        time.sleep(interval)
                        duration -= interval

        return wrapped
