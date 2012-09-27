from testcases import HQSeleniumTestCase
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import re


class AdminUserTestCase(HQSeleniumTestCase):
    username = 'mwhite+test@dimagi.com'
    password = 'password'
    base_url = 'http://localhost:8000'
    test_project = 'test'

    @classmethod
    def setUpClass(cls):
        super(AdminUserTestCase, cls).setUpClass()
        cls.assertIn('Projects', cls.page_source)
        cls.find_element_by_link_text(cls.test_project).click()


class ReportsTestCase(AdminUserTestCase):

    @classmethod
    def setUpClass(cls):
        super(ReportsTestCase, cls).setUpClass()
        cls.find_element_by_link_text('Reports').click()
        cls.assertIn('Project Reports', cls.page_source)

    @classmethod
    def generate_test(cls, report_name):
        def test(self):
            self.find_element_by_link_text(report_name).click()

            try:
                WebDriverWait(self.driver, 3).until(
                    lambda d: d.find_element_by_link_text("Hide Filter Options")
                )
            except TimeoutException:
                WebDriverWait(self.driver, 5).until(
                    lambda d: d.find_element_by_link_text("Show Filter Options")
                ).click()
                # Selenium thinks Update Filters button is disabled without this 
                time.sleep(.5)

            WebDriverWait(self.driver, 3).until(
                lambda d: d.find_element_by_xpath(
                    "//div[@class='form-actions']/button"
                )
            ).click()

            def loading_report(d):
                if 'Fetching additional data' in d.page_source:
                    return True

                try:
                    elem = d.find_element_by_xpath("//div[@class='hq-loading']")
                    return elem.is_displayed()
                except NoSuchElementException:
                    pass

                return False

            WebDriverWait(self.driver, 3).until_not(loading_report)

        return test

report_names = (
    'Case Activity',
    'Submissions By Form',
    'Daily Form Submissions',
    'Daily Form Completions',
    'Form Completion Trends',
    'Form Completion vs. Submission Trends',
    'Submission Times',
    'Submit Distribution',

    'Submit History',
    'Case List',

    'Export Submissions to Excel',
    'Export Cases, Referrals, & Users',
    'De-Identified Export',

    'Application Status',
    'Raw Forms, Errors & Duplicates',
    'Errors & Warnings Summary',
    'Device Log Details'
)

for report_name in report_names:
    name = re.sub(r"[^a-z\s]", "", report_name.lower()).replace(" ", "_")
    method = "test_%s" % name
    setattr(ReportsTestCase, method, ReportsTestCase.generate_test(report_name))

