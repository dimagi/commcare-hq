from __future__ import absolute_import

import unittest
from receiver.submitresponse import SubmitResponse


class SubmitResponseTestCase(unittest.TestCase):
    
    # Expected responses.  This isn't a great test since
    # the order is currently somewhat arbitrary (alphabetical)
    # and this will fall if that changes, however this
    # is slightly better than printing the responses and 
    # looking at them, and re-parsing the XML kind of
    # defeats the purpose of 'unit' test.
    
    BASIC_RESPONSE="""
<?xml version='1.0' encoding='UTF-8'?>
<OpenRosaResponse>
  <SubmissionStatusCode>200</SubmissionStatusCode>
</OpenRosaResponse>"""

    FULL_RESPONSE="""
<?xml version='1.0' encoding='UTF-8'?>
<OpenRosaResponse>
  <FormsSubmittedToday>7</FormsSubmittedToday>
  <OpenRosaStatus>Nice submission!</OpenRosaStatus>
  <OpenRosaStatusCode>2000</OpenRosaStatusCode>
  <SubmissionId>37</SubmissionId>
  <SubmissionStatusCode>200</SubmissionStatusCode>
  <TotalFormsSubmitted>45</TotalFormsSubmitted>
</OpenRosaResponse>"""
    
    NULL_RESPONSE="""
<?xml version='1.0' encoding='UTF-8'?>
<OpenRosaResponse>
  <FormsSubmittedToday>8</FormsSubmittedToday>
  <OpenRosaStatusCode>2001</OpenRosaStatusCode>
  <SubmissionId>38</SubmissionId>
  <SubmissionStatusCode>200</SubmissionStatusCode>
  <TotalFormsSubmitted>456</TotalFormsSubmitted>
</OpenRosaResponse>"""
    
    CUSTOM_RESPONSE="""
<?xml version='1.0' encoding='UTF-8'?>
<OpenRosaResponse>
  <AnotherOne>Value2</AnotherOne>
  <MyCustomAttribute>My Custom Value</MyCustomAttribute>
  <OpenRosaStatusCode>2003</OpenRosaStatusCode>
  <SubmissionStatusCode>200</SubmissionStatusCode>
</OpenRosaResponse>"""

    def setup(self):
        pass

    def tearDown(self):
        pass
    
    def testBasicXml(self):
        # base case
        resp = SubmitResponse(200)
        self.assertEqual(self.BASIC_RESPONSE.strip(), str(resp).strip())
        # fully filled out submission
        resp = SubmitResponse(200, 2000, "Nice submission!", 
                              37, 7, 45)
        self.assertEqual(self.FULL_RESPONSE.strip(), str(resp).strip())
        # null fields 
        resp = SubmitResponse(200, 2001, None, 
                              38, 8, 456)
        self.assertEqual(self.NULL_RESPONSE.strip(), str(resp).strip())
        # custom arguments
        resp = SubmitResponse(status_code=200, or_status_code=2003, 
                              MyCustomAttribute="My Custom Value",
                              AnotherOne="Value2")
        self.assertEqual(self.CUSTOM_RESPONSE.strip(), str(resp).strip())
        
        