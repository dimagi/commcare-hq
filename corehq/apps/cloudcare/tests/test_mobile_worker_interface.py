from testcases import HQSeleniumTestCase


class MobileWorkerTestCase(HQSeleniumTestCase):
    username = 'user@test.commcarehq.org'
    password = 'password'
    base_url = 'http://localhost:8000'

    def setUp(self):
        super(MobileWorkerTestCase, self).setUp()
        self.assertIn('Apps', self.page_source)

    def test_foo(self):

        import time
        time.sleep(1)
