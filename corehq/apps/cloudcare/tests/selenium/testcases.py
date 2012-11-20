from corehq.apps.selenium.testcases import MobileWorkerTestCase
from selenium.common.exceptions import NoSuchElementException
from corehq.apps import selenium

DEFAULT_OPEN_FORM_WAIT_TIME = 10
DEFAULT_SUBMIT_FORM_WAIT_TIME = 5


class CloudCareQuestion(object):
    """
    Selenium WebElement wrapper class with convenience methods for question
    divs.

    """
    def __init__(self, element):
        self.element = element

    def __getattr__(self, name):
        return getattr(self.element, name)

    @property
    def input(self):
        return self.find_element_by_xpath("div[@id='widget']/input")

    def set_value(self, value):
        self.input.send_keys(value)
        # todo: click outside to trigger validation, and handle non-text inputs


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

    case_list_forms = []
    teardown_close_case_form = None

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
        if cls.teardown_close_case_form:
            cls.close_all_cases(cls.teardown_close_case_form)

        super(CloudCareTestCase, cls).tearDownClass()

    @classmethod
    def open_form(cls, name):
        if name in cls.case_list_forms:
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
    def find_question(cls, name=None):
        if name:
            xpath = "//span[@id='caption' and text()='%s']/.." % name
        else:
            # find any question
            xpath = "//span[@id='caption']/.."
        question = cls.driver.find_element_by_xpath(xpath)
            
        return CloudCareQuestion(question)

    @classmethod
    def submit_form(cls, expect_success=True):
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
    def close_all_cases(cls, close_case_form_name):
        while True:
            cls.open_form(close_case_form_name)
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
