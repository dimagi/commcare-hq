from __future__ import absolute_import
from corehq.motech.repeaters.views import AddCaseRepeaterView


class AadhaarDemoAuthRepeaterView(AddCaseRepeaterView):
    urlname = 'icds_aadhaar_demo_auth'
    page_title = "ICDS Aadhaar Demo Auth"
    page_name = "ICDS Aadhaar Demo Auth"
