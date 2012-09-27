from dimagi.utils.django.test import SeleniumTestCase, NoSuchElementException
import random
import string


def random_string(length=16):
    return ''.join([random.choice(string.ascii_uppercase + string.digits)
                    for i in range(length)])


class HQSeleniumTestCase(SeleniumTestCase):
    base_url = None
    user = None
    password = None

    @classmethod
    def setUpClass(cls):
        super(HQSeleniumTestCase, cls).setUpClass()
        cls.get('/')
        cls.driver.find_element_by_link_text("Sign In").click()

        user = cls.driver.find_element_by_name("username")
        user.send_keys(cls.user)
        pw = cls.driver.find_element_by_name("password")
        pw.send_keys(cls.password)
        pw.submit()


class CloudCareTestCase(HQSeleniumTestCase):
    base_url = "http://localhost:8000"
    user = 'user@mike.commcarehq.org'
    password = 'password'
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
            self.find_element_by_xpath("//*[@id='dataTables-filter-box']",
                                       duration=10)
        else:
            self.find_element_by_xpath("//section//div[@id='form']",
                                       duration=10)

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


class BasicTestAppTestCase(CloudCareTestCase):
    app_name = 'Basic Test'
    
    case_list_forms = ['Update Case', 'Close Case']

    def setUp(self):
        super(BasicTestAppTestCase, self).setUp()
        
        try:
            self.find_element_by_xpath("//nav[@id='form-list']/ul")
            # module has already been clicked on
        except NoSuchElementException:
            # click on the module, after waiting for the app to load
            self.wait_until(
                lambda driver: len(driver.find_elements_by_link_text(self.app_name)) > 1
            )
        
            self.find_elements_by_link_text(self.app_name)[1].click()

    def create_case(self):
        self.open_form('New Case')
        name = random_string()
        self.find_element_by_id('textfield').send_keys(name)
        self.submit_form()

        return name

    def test_first_form(self):
        self.open_form('First Form')

        name = random_string()
        self.find_element_by_id('textfield').send_keys(name)
        self.submit_form()
        
        self.open_form('Update Case')
        self.assertNotIn(name, self.page_source)

    def test_new_case(self):
        name = self.create_case()
        self.open_form('Update Case')
        self.click_case(name)
        self.find_element_by_id('case-details')
        tds = self.find_elements_by_xpath("//section[@id='case-details']//td")
        self.assertTrue(len(tds) > 0)
        for td in tds:
            self.assertTrue(td.text == '?' or td.text == name)

    def test_update_case(self):
        name = self.create_case()

        self.open_form('Update Case')
        self.click_case(name)
        self.find_element_by_link_text('Enter Update Case').click()

        self.find_element_by_xpath("//span[.='Blue']").click()
        self.submit_form()

        self.open_form('Update Case')
        tds = self.find_elements_by_xpath("//section[@id='case-details']//td")
        self.assertTrue(len(tds) > 0)
        flag = False
        for td in tds:
            if td.text == name:
                flag = True
            if flag:
                self.assertEqual('blue', td.text)
                break

    def test_close_case(self):
        name = self.create_case()
        self.open_form('Close Case')
        self.click_case(name)
        self.find_element_by_link_text('Enter Close Case').click()
        self.find_element_by_id('textfield').send_keys('reason for closing')
        self.submit_form()
        self.open_form('Update Case')
        self.assertNotIn(name, self.page_source)

