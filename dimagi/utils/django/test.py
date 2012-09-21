from selenium import webdriver
from django.test import TestCase


class SeleniumTestCase(TestCase):
    """
    A test class that sets up a Chrome WebDriver and lets you call
    webdriver methods directly on the test instance.

    """
    base_url = ''

    @classmethod
    def get(cls, path):
        return cls.driver.get(cls.base_url + path)

    def __getattr__(self, name):
        return getattr(self.driver, name)

    @classmethod
    def setUpClass(cls):
        super(SeleniumTestCase, cls).setUpClass()
        cls.driver = webdriver.Chrome()

    @classmethod
    def tearDownClass(cls):
        super(SeleniumTestCase, cls).tearDownClass()
        cls.driver.quit()

try:
    # django 1.4
    from django.test import LiveServerTestCase
except ImportError:
    try:
        from django_liveserver.testcases import LiveServerTestCase
    except ImportError:
        import logging
        logging.warning("LiveServerTestCase not available")
