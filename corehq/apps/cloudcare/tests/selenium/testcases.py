from corehq.apps.selenium.testcases import MobileWorkerTestCase
from selenium.common.exceptions import NoSuchElementException


class CloudCareTestCase(MobileWorkerTestCase):
    app_name = None

    case_list_forms = None

    @classmethod
    def setUpClass(cls):
        super(CloudCareTestCase, cls).setUpClass()

        cls.driver.find_element_by_link_text("CloudCare").click()

        # click on the application
        cls.driver.find_elements_by_link_text(cls.app_name)[0].click()

    def open_form(self, name):
        self.find_element_by_link_text(name).click()

        # ensure that the form/case list has loaded
        if name in self.case_list_forms:
            xpath = "//*[@id='dataTables-filter-box']"
        else:
            xpath = "//section//div[@id='form']"
        
        self.find_element_by_xpath(xpath, duration=10)

    def submit_form(self, expect_success=True):
        self.find_element_by_id('submit').click()

        if expect_success:
            # there seems to be a bug in CloudCare which requires you to click
            # Submit twice.  That should be fixed, and this try-except removed
            try:
                self.find_element_by_xpath(
                    "//*[@class='alert alert-success' and not(contains(@style, 'display: none'))]"
                )
            except NoSuchElementException:
                self.find_element_by_id('submit').click()
                self.find_element_by_xpath(
                    "//*[@class='alert alert-success' and not(contains(@style, 'display: none'))]"
                )

    def click_case(self, name):
        for elem in self.find_elements_by_xpath("//section//td"):
            if elem.text == name:
                return elem.click()
        
        self.assertTrue(False)
