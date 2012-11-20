"""
Tests for applications in the 'corpora' domain.

"""

from testcases import CloudCareTestCase


class BasicTestTestCase(CloudCareTestCase):
    app_name = 'Basic Test'
    module_name = 'Basic Test'
    case_list_forms = ['Update Case', 'Close Case']
    teardown_close_case_form = 'Close Case'

    def _create_case(self):
        self.open_form('New Case')
        name = self.random_string()
        self.find_question('Enter your name').set_value(name)
        self.submit_form()

        return name

    def test_first_form(self):
        self.open_form('First Form')
        name = self.random_string()
        self.find_question('Enter your name').set_value(name)
        self.submit_form()
        
        self.open_form('Update Case')
        self.assertNotIn(name, self.page_source)

    def test_new_case(self):
        name = self._create_case()
        self.open_form('Update Case')
        self.click_case(name)
        self.find_element_by_id('case-details')
        tds = self.find_elements_by_xpath("//section[@id='case-details']//td")
        self.assertTrue(len(tds) > 0)
        for td in tds:
            self.assertTrue('---' in td.text or td.text == name)

    def test_update_case(self):
        name = self._create_case()

        self.open_form('Update Case')
        self.click_case(name)
        self.find_element_by_link_text('Enter Update Case').click()

        self.find_element_by_xpath("//span[text()='Blue']").click()
        self.submit_form()

        self.open_form('Update Case')
        self.click_case(name)
        self.find_element_by_xpath(
            "//section[@id='case-details']//td[text()='blue']"
        )

    def test_close_case(self):
        name = self._create_case()
        self.open_form('Close Case')
        self.click_case(name)
        self.find_element_by_link_text('Enter Close Case').click()
        self.find_question('Reason for Closing').set_value('foo')
        self.submit_form()
        self.open_form('Update Case')
        self.assertNotIn(name, self.page_source)
