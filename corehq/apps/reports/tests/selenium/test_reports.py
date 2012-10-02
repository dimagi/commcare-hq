from corehq.apps.selenium.testcases import AdminUserTestCase
from selenium.common.exceptions import NoSuchElementException
import re


class ReportsTestCase(AdminUserTestCase):

    @classmethod
    def setUpClass(cls):
        super(ReportsTestCase, cls).setUpClass()
        cls.driver.find_element_by_link_text('Reports').click()
        assert 'Project Reports' in cls.driver.page_source

    @classmethod
    def generate_test(cls, report_name):

        def loading_report(d):
            # todo: make sure this check doesn't need to have a wait before
            # it. It's very fast, but it might.
            if 'Fetching additional data' in d.page_source:
                return True

            try:
                elem = d.find_element_by_xpath("//div[@class='hq-loading']")
                return elem.is_displayed()
            except NoSuchElementException:
                pass

            return False

        def test(self):
            self.find_element_by_link_text(report_name).click()

            try:
                self.find_element_by_link_text("Hide Filter Options",
                                               duration=2)
            except NoSuchElementException:
                self.find_element_by_link_text("Show Filter Options").click()

            self.find_element_by_xpath(
                "//div[@class='form-actions']/button"
            ).click()

            self.wait_until_not(loading_report)

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
    setattr(ReportsTestCase, "test_%s" % name,
            ReportsTestCase.generate_test(report_name))

