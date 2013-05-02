from corehq.apps.smsforms.app import get_responses
from corehq.apps.sms.models import SMSLog

CONTACT_ID = "sms_test_contact_id"
DOMAIN = 'test-domain'
        
class MockContact(object):
    """
    Mock contact implements the contact API
    """
    def __init__(self, id, username, language=""):
        self.get_id = id
        self.raw_username = username
        self.language = language
        
    def get_language_code(self):
        return self.language


def q_and_a(testcase, answer, expected_response, domain=DOMAIN, 
            contact_id=CONTACT_ID, print_output=True):
            
    responses = get_responses(SMSLog(couch_recipient=contact_id, domain=domain,
                                     text=answer))
    [answer_back] = responses
    testcase.assertEqual(expected_response, answer_back, 
                         "Response to '%s' expected '%s' but was '%s'" % \
                         (answer, expected_response, answer_back))
    if print_output:
        print "%s -> %s" % (answer, answer_back)