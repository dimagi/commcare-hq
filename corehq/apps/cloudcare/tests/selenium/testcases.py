from dimagi.utils.django.test import SeleniumWrapper
from corehq.apps.selenium.testcases import MobileWorkerTestCase
from selenium.common.exceptions import NoSuchElementException
from corehq.apps import selenium

DEFAULT_OPEN_FORM_WAIT_TIME = 10
DEFAULT_SUBMIT_FORM_WAIT_TIME = 5


class CloudCareQuestion(object):
    """
    Selenium WebElement wrapper class with convenience methods for questions.

    """
    def __init__(self, element):
        # element is a fully loaded question - we can assume any finds can
        # return immediately
        self.element = SeleniumWrapper(element)

    def __getattr__(self, name):
        return getattr(self.element, name)

    def set_value(self, value):
        try:
            # text input
            self.find_element_by_xpath(
                "div[@id='widget']/input", duration=0
            ).send_keys(value)
        except NoSuchElementException:
            # radio buttons
            self.find_element_by_xpath(
                "div[@id='widget']//span[@id='label' and text()='%s']" % value,
                duration=0
            ).click()

            # todo: other non-text inputs (?)

        # todo: click outside to trigger validation

class CloudCareTestCase(MobileWorkerTestCase):
    """
    Base TestCase for cloudcare with convenience methods.

    All methods should be classmethods so they are available to each other and
    setupClass() and tearDownClass() (including for subclasses).

    """
    app = selenium.get_app('cloudcare')
    open_form_wait_time = app.get('OPEN_FORM_WAIT_TIME',
                                  DEFAULT_OPEN_FORM_WAIT_TIME)
    submit_form_wait_time = app.get('SUBMIT_FORM_WAIT_TIME',
                                    DEFAULT_SUBMIT_FORM_WAIT_TIME)

    app_name = None
    module_name = None
    update_case_form = None
    close_case_form = None

    @classmethod
    def setUpClass(cls):
        super(CloudCareTestCase, cls).setUpClass()

        cls.driver.find_element_by_link_text("CloudCare").click()

        # click on the application
        cls.driver.find_element_by_xpath(
            "//nav[@id='app-list']//a[text()='%s']" % cls.app_name
        ).click()

        # click on the module
        cls.driver.find_element_by_xpath(
            "//nav[@id='module-list']//a[text()='%s']" % cls.module_name
        ).click()

    @classmethod
    def tearDownClass(cls):
        if cls.close_case_form:
            cls.close_all_cases()

        super(CloudCareTestCase, cls).tearDownClass()

    @classmethod
    def open_form(cls, name):
        if name in [cls.update_case_form, cls.close_case_form]:
            xpath = "//*[@id='dataTables-filter-box']"
        else:
            xpath = "//section//div[@id='form']"

        click_form = lambda: cls.driver.find_element_by_link_text(name).click()
        find_form = lambda: cls.driver.find_element_by_xpath(
            xpath, duration=cls.open_form_wait_time)

        click_form()
        # ensure that the form/case list has loaded
        try:
            find_form()
        except NoSuchElementException:
            # retry in case that form was already open and we closed it
            click_form()
            find_form()

    @classmethod
    def submit_form(cls, expect_success=True):
        """Submit the currently open form."""

        success = "//*[@class='alert alert-success' and not(contains(@style, 'display: none'))]"
        
        # wait until any success alerts from previous form submissions go away
        cls.driver.wait_until_not(lambda d: d.find_element_by_xpath(success))

        # todo: make single click work
        cls.driver.find_element_by_id('submit').click()
        cls.driver.sleep(1)
        cls.driver.find_element_by_id('submit').click()

        if expect_success:
            cls.driver.find_element_by_xpath(
                success, duration=cls.submit_form_wait_time)

    @classmethod
    def click_case(cls, name):
        cls.driver.find_element_by_xpath(
            "//section//td[text()='%s']" % name).click()

    @classmethod
    def enter_update_case(cls, name):
        cls.click_case(name)
        cls.driver.find_element_by_link_text('Enter Update Case').click()

    @classmethod
    def enter_close_case(cls, name):
        cls.click_case(name)
        cls.driver.find_element_by_link_text('Enter Close Case').click()

    @classmethod
    def find_question(cls, name=None):
        """
        Returns a CloudCareQuestion wrapper instance for the visible question
        with the label 'name'.

        """
        if name:
            xpath = "//span[@id='caption' and text()='%s']/.." % name
        else:
            # find any question
            xpath = "//span[@id='caption']/.."
        question = cls.driver.find_element_by_xpath(xpath)
            
        return CloudCareQuestion(question)

    @classmethod
    def get_case_details(cls, name):
        """
        Returns a dictionary of case attributes as displayed on the update case
        form.
        
        """
        cls.open_form(cls.update_case_form)
        cls.click_case(name)

        trs = cls.driver.find_elements_by_xpath(
            "//section[@id='case-details']//tbody//tr")

        details = {}
        for tr in trs:
            name = tr.find_element_by_tag_name('th').text
            value = tr.find_element_by_tag_name('td').text
            details[name] = value

        return details

    @classmethod
    def get_open_case_names(cls):
        cls.open_form(cls.update_case_form)

        tds = cls.driver.find_elements_by_xpath(
            "//section[@id='case-list']//tbody//tr/td[position()=1]")

        return [td.text for td in tds]
   
    @classmethod
    def close_all_cases(cls):
        while True:
            cls.open_form(cls.close_case_form)
            try:
                cls.driver.find_element_by_xpath(
                    "//section[@id='case-list']//td[not(contains(@class, 'dataTables_empty'))]",
                    duration=0
                ).click()
            except NoSuchElementException:
                return
            
            cls.driver.find_element_by_link_text('Enter Close Case').click()
            cls.find_question()
            cls.submit_form()
