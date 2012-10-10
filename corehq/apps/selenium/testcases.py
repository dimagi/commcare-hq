from dimagi.utils.django.test import SeleniumTestCase
from django.conf import settings
from corehq.apps import selenium
import random
import string

DEFAULT_BROWSER = 'Chrome'


class HQSeleniumTestCase(SeleniumTestCase):
    """
    Base test case for testing things that require logging in to the HQ web
    interface.

    """
    browser = settings.SELENIUM_SETUP.get('BROWSER', DEFAULT_BROWSER)
    remote_url = settings.SELENIUM_SETUP.get('REMOTE_URL', None)

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

    @classmethod
    def setUpClass(cls):
        user = selenium.get_user('ADMIN')
        cls.username = user.USERNAME
        cls.password = user.PASSWORD
        cls.base_url = user.URL
        cls.project = user.PROJECT
        cls.is_superuser = user.IS_SUPERUSER

        super(AdminUserTestCase, cls).setUpClass()


class WebUserTestCase(_WebUserTestCase):
    
    force_non_admin_user = False

    @classmethod
    def setUpClass(cls):
        user = selenium.get_user('WEB_USER', exact=cls.force_non_admin_user)
        cls.username = user.USERNAME
        cls.password = user.PASSWORD
        cls.base_url = user.URL
        cls.project = user.PROJECT
        cls.is_superuser = user.IS_SUPERUSER

        super(WebUserTestCase, cls).setUpClass()


class MobileWorkerTestCase(HQSeleniumTestCase):

    @classmethod
    def setUpClass(cls):
        user = selenium.get_user('MOBILE_WORKER')
        cls.username = user.USERNAME
        cls.password = user.PASSWORD
        cls.base_url = user.URL

        super(MobileWorkerTestCase, cls).setUpClass()
