from dimagi.utils.django.test import SeleniumTestCase
from django.conf import settings
import random
import string


class HQSeleniumTestCase(SeleniumTestCase):
    """
    Base test case for testing things that require logging in to the HQ web
    interface.

    """
    username = None
    password = None
    base_url = None

    @classmethod
    def setUpClass(cls):
        """
        Log in to HQ as the user specified by self.username, self.password.

        """

        super(HQSeleniumTestCase, cls).setUpClass()

        cls.driver.get('/')
        cls.driver.find_element_by_link_text("Sign In").click()

        user = cls.driver.find_element_by_name('username')
        user.send_keys(cls.username)
        pw = cls.driver.find_element_by_name('password')
        pw.send_keys(cls.password)
        pw.submit()

        # todo: figure out what common denominator about the post-login HQ html
        # to assert here

    @classmethod
    def random_string(cls, length=16):
        return ''.join([random.choice(string.ascii_uppercase + string.digits)
                        for i in range(length)])


class AdminUserTestCase(HQSeleniumTestCase):
    username = settings.TEST_ADMIN_USERNAME
    password = settings.TEST_ADMIN_PASSWORD
    base_url = settings.TEST_BASE_URL
    test_project = settings.TEST_ADMIN_PROJECT

    @classmethod
    def setUpClass(cls):
        super(AdminUserTestCase, cls).setUpClass()
        assert 'Projects' in cls.driver.page_source
        cls.driver.find_element_by_link_text(cls.test_project).click()


class MobileWorkerTestCase(HQSeleniumTestCase):
    username = settings.TEST_MOBILE_WORKER_USERNAME
    password = settings.TEST_MOBILE_WORKER_PASSWORD
    base_url = settings.TEST_BASE_URL
