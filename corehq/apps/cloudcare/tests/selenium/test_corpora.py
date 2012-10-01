from testcases import CloudCareTestCase
from selenium.common.exceptions import NoSuchElementException
import random
import string


def random_string(length=16):
    return ''.join([random.choice(string.ascii_uppercase + string.digits)
                    for i in range(length)])


class BasicTestAppTestCase(CloudCareTestCase):
    """
    Tests for the 'Basic Test' application on the corpora domain.
    
    """
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
        flag = False
        for td in tds:
            if td.text == name:
                self.assertEqual('blue', td.text)
                flag = True
                break

        self.assertTrue(flag)

    def test_close_case(self):
        name = self.create_case()
        self.open_form('Close Case')
        self.click_case(name)
        self.find_element_by_link_text('Enter Close Case').click()
        self.find_element_by_id('textfield').send_keys('reason for closing')
        self.submit_form()
        self.open_form('Update Case')
        self.assertNotIn(name, self.page_source)

