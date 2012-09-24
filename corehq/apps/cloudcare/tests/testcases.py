from dimagi.utils.django.test import SeleniumTestCase, LiveServerTestCase


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

        cls.get('/')
        cls.find_element_by_link_text("Sign In").click()

        user = cls.find_element_by_name('username')
        user.send_keys(cls.username)
        pw = cls.find_element_by_name('password')
        pw.send_keys(cls.password)
        pw.submit()

        # todo: figure out what common denominator about the post-login HQ html
        # to assert here


class MockHQSeleniumTestCase(HQSeleniumTestCase, LiveServerTestCase):
    
    @classmethod
    def setUpClass(cls):
        LiveServerTestCase.setUpClass(cls)
        cls.base_url = cls.live_server_url
        HQSeleniumTestCase.setUpClass(cls)
