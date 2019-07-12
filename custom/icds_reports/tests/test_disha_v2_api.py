from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import TestCase
from custom.icds_reports.utils.data_accessor import get_disha_api_v2_data


class DishaV2ApiTest(TestCase):

    def test_file_content(self):
        state_id = 'st1'
        month = '2017-05-01'

        data = get_disha_api_v2_data(state_id, month)

        self.assertMultiLineEqual("""<?xml version="1.0" encoding="UTF-8"?>
    <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2001/12/soap-envelope"
    SOAP-ENV:encodingStyle="http://www.w3.org/2001/12/soap-encoding">
       <SOAP-ENV:Header />
       <SOAP-ENV:Body>
          <state>st1</state>
          <month>2017-05-01</month>
          <num_launched_awcs>9</num_launched_awcs>
          <num_households_registered>3633</num_households_registered>
          <pregnant_enrolled>70</pregnant_enrolled>
          <lactating_enrolled>87</lactating_enrolled>
          <children_enrolled>618</children_enrolled>
          <bf_at_birth>1</bf_at_birth>
          <ebf_in_month>17</ebf_in_month>
          <cf_in_month>54</cf_in_month>
       </SOAP-ENV:Body>
    </SOAP-ENV:Envelope>""", data)
