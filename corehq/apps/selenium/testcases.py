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


class _WebUserTestCase(HQSeleniumTestCase):
    project = None
    is_superuser = None

    @classmethod
    def setUpClass(cls):
        super(_WebUserTestCase, cls).setUpClass()

        if cls.is_superuser:
            assert ('Projects' in cls.driver.page_source or
                    'Create a New Project' in cls.driver.page_source)
            cls.driver.get('/a/' + cls.project)
        else:
            assert 'Projects' in cls.driver.page_source
            cls.driver.find_element_by_link_text(cls.project).click()


class AdminUserTestCase(_WebUserTestCase):
    username = settings.TEST_ADMIN_USERNAME
    password = settings.TEST_ADMIN_PASSWORD
    base_url = settings.TEST_ADMIN_URL
    project = settings.TEST_ADMIN_PROJECT
    is_superuser = settings.TEST_ADMIN_IS_SUPERUSER


class WebUserTestCase(_WebUserTestCase):
    username = settings.TEST_WEB_USER_USERNAME
    password = settings.TEST_WEB_USER_PASSWORD
    base_url = settings.TEST_WEB_USER_URL
    project = settings.TEST_WEB_USER_PROJECT
    is_superuser = settings.TEST_WEB_USER_IS_SUPERUSER


class MobileWorkerTestCase(HQSeleniumTestCase):
    username = settings.TEST_MOBILE_WORKER_USERNAME
    password = settings.TEST_MOBILE_WORKER_PASSWORD
    base_url = settings.TEST_MOBILE_WORKER_URL
