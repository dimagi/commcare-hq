from selenium import selenium
import unittest, time, re, urllib2
from post import *
import os
import sys
import time


local = True # semi convenient flip-flop for local versus remote testing
if local:
    sites = {"http://localhost:8000": ["brian", "test",
                                   "localhost:8000", "Pathfinder"]}
else: 
    sites = {"http://staging.commcarehq.org": ["brian", "test",
                                        "staging.commcarehq.org", "BRAC"]}

class testingPost(unittest.TestCase):

    def setUp(self):
        self.verificationErrors = []
        self.selenium = selenium("localhost", 4444, "*firefox", server)
        self.selenium.start()
    
    def test_testingPost(self):
        sel = self.selenium
        # get to the login page
        sel.open("/no_permissions?next=/")
        sel.click("link=Log in to CommcareHQ")
        sel.wait_for_page_to_load("30000")
        sel.type("id_username", user)
        sel.type("id_password", passw)
        sel.click("//button[@type='submit']")
        
        # redirects to domain selection, so just click through
        sel.wait_for_page_to_load("30000")
        sel.click("//button[@type='submit']")
        
        # testing creation of xform
        sel.wait_for_page_to_load("30000")
        sel.click("link=XForms")
        time.sleep(3)
        if sel.is_text_present("Sample Form 1"):
            self.delete_xform(sel)
        time.sleep(3)
        path = os.path.join(sys.path[0], "sample_form.xhtml")
        sel.type("id_file", path)
        sel.type("id_form_display_name", "Sample Form 1")
        sel.click("//div[@id='xform-register-block']/form/ul/li[3]/input")
        sel.wait_for_page_to_load("30000")
        sel.click("//input[@value=\"Yes, I'm sure\"]")
        sel.wait_for_page_to_load("30000")
        try: self.failUnless(sel.is_text_present("Sample Form 1"), "New form showed in XForm Listing")
        except AssertionError, e: self.verificationErrors.append(str(e))
        

        # testing basic submission of xml (or file) and diff against actual
        # copy
        temp_file_name = 'testupload_tmp.xml'
        submission_number = post(serverhost, domain, temp_file_name)
        sel.click("link=Submissions")
        sel.wait_for_page_to_load("30000")
        time.sleep(3)
        sel.click("link=%s" % submission_number)
        sel.wait_for_page_to_load("30000")
        time.sleep(2)
        sel.click("link=view full raw submission")
        time.sleep(2)
        file = None
        try:
            file = open(temp_file_name, 'r')
            xml_present = file.read()
            self.failUnless(sel.is_text_present(xml_present), "Correct XML was present in file")
        except AssertionError, e: 
            self.verificationErrors.append(str(e))
        finally:
            if file: file.close()
        os.remove(temp_file_name)
        
        #test to see if form has been processed
        sel.open("/receiver/review")
        sel.wait_for_page_to_load("30000")
        time.sleep(3)
        sel.click("link=%s" % submission_number)
        sel.wait_for_page_to_load("30000")
        try: self.failUnless(sel.is_text_present("view form data"), 
                             "xml submission was parsed and matched to form")
        except AssertionError, e: self.verificationErrors.append(str(e))

        #test Xform deletion
        self.delete_xform(sel)

    def tearDown(self):
        self.selenium.stop()
        self.assertEqual([], self.verificationErrors)

    def delete_xform(self, sel):
        sel.open("/xforms/")
        sel.wait_for_page_to_load("30000")
        sel.click("//div[@onclick=\"show_forms('http://dev.commcarehq.org/BRAC/CHP/coakley', '#formlist');\"]")
        sel.click("//div[@onclick=\"show_forms('http://dev.commcarehq.org/BRAC/CHP/coakley', '#formlist');\"]")
        time.sleep(2)
        sel.click("link=drop this form")
        sel.wait_for_page_to_load("30000")
        sel.click("//input[@value=\"Yes, I'm sure\"]")
        sel.wait_for_page_to_load("30000")
        try: self.failUnless(not sel.is_text_present("Sample Form 1"),
                             "Deleted form was removced from xform listing")
        except AssertionError, e: self.verificationErrors.append(str(e))
 
if __name__ == "__main__":
    for key, value in sites.items():
        server = key
        user = value[0]
        passw = value[1]
        serverhost = value[2]
        domain = value[3]
        unittest.main()
