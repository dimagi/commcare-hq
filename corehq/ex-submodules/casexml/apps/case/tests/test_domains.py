from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from django.test.utils import override_settings

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.tests.utils import use_sql_backend, FormProcessorTestUtils

ALICE_XML = """<?xml version='1.0' ?>
<data xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="http://openrosa.org/formdesigner/D95E58BD-A228-414F-83E6-EEE716F0B3AD">
    <name>Dinkle</name>
    <join_date>2010-08-28</join_date>
    <n0:case case_id="ddb8e2b3-7ce0-43e4-ad45-domain-test" user_id="user-xxx-alice" date_modified="2013-04-19T16:52:04.304-04" xmlns:n0="http://commcarehq.org/case/transaction/v2">
        <n0:create>
            <n0:case_name>Dinkle</n0:case_name>
            <n0:owner_id>da77a254-56dd-11e0-a55d-005056aa7fb5</n0:owner_id>
            <n0:case_type>member</n0:case_type>
        </n0:create>
        <n0:update>
            <n0:join_date>2010-08-28</n0:join_date>
        </n0:update>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>A00000245706EE</n1:deviceID>
        <n1:timeStart>2013-04-19T16:51:13.162-04</n1:timeStart>
        <n1:timeEnd>2013-04-19T16:52:13.162-04</n1:timeEnd>
        <n1:username>alice</n1:username>
        <n1:userID>da77a254-56dd-11e0-a55d-005056aa7fb5</n1:userID>
        <n1:instanceID>a588a637-cde0-43ad-a046-4c508102009d</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">CommCare ODK, version "2.4.1"(10083). App v19. CommCare Version 2.4. Build 10083, built on: March-12-2013</n2:appVersion>
    </n1:meta>
</data>"""

EVE_XML = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="New Form" xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="http://openrosa.org/formdesigner/1DFD8610-91E3-4409-BF8B-02D3B4FF3530">
    <plan_to_buy_gun>no</plan_to_buy_gun>
    <n0:case case_id="ddb8e2b3-7ce0-43e4-ad45-domain-test" user_id="user-xxx-eve" date_modified="2013-04-19T16:53:02.799-04" xmlns:n0="http://commcarehq.org/case/transaction/v2">
        <n0:update>
            <n0:plan_to_buy_gun>no</n0:plan_to_buy_gun>
        </n0:update>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>A00000245706EE</n1:deviceID>
        <n1:timeStart>2013-04-19T16:52:41.000-04</n1:timeStart>
        <n1:timeEnd>2013-04-19T16:53:02.799-04</n1:timeEnd>
        <n1:username>eve</n1:username>
        <n1:userID>user-xxx-eve</n1:userID>
        <n1:instanceID>b58df19c-efd5-4ecf-9581-65dda8b8787c</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">CommCare ODK, version "2.4.1"(10083). App v19. CommCare Version 2.4. Build 10083, built on: March-12-2013</n2:appVersion>
    </n1:meta>
</data>"""

ALICE_UPDATE_XML = """<?xml version='1.0' ?>
<data uiVersion="1" version="17" name="New Form" xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="http://openrosa.org/formdesigner/1DFD8610-91E3-4409-BF8B-02D3B4FF3530">
    <plan_to_buy_gun>no</plan_to_buy_gun>
    <n0:case case_id="ddb8e2b3-7ce0-43e4-ad45-domain-test" user_id="user-xxx-alice" date_modified="2013-04-19T16:53:02.799-04" xmlns:n0="http://commcarehq.org/case/transaction/v2">
        <n0:update>
            <n0:plan_to_buy_gun>no</n0:plan_to_buy_gun>
        </n0:update>
    </n0:case>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>A00000245706EE</n1:deviceID>
        <n1:timeStart>2013-04-19T16:52:41.000-04</n1:timeStart>
        <n1:timeEnd>2013-04-19T16:53:02.799-04</n1:timeEnd>
        <n1:username>alice</n1:username>
        <n1:userID>user-xxx-alice</n1:userID>
        <n1:instanceID>b58df19c-efd5-4ecf-9581-65dda8b8787cXXX</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">CommCare ODK, version "2.4.1"(10083). App v19. CommCare Version 2.4. Build 10083, built on: March-12-2013</n2:appVersion>
    </n1:meta>
</data>"""


ALICE_DOMAIN = 'domain1'
EVE_DOMAIN = 'domain2'


@override_settings(CASEXML_FORCE_DOMAIN_CHECK=True)
class DomainTest(TestCase):

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers()
        super(DomainTest, self).tearDown()

    def test_cant_own_case(self):
        result_alice = submit_form_locally(ALICE_XML, ALICE_DOMAIN)
        result_eve = submit_form_locally(EVE_XML, EVE_DOMAIN)

        self.assertIn('IllegalCaseId', result_eve.response.content)
        self.assertNotIn('plan_to_buy_gun', result_alice.case.dynamic_case_properties())

        result_alice_update = submit_form_locally(ALICE_UPDATE_XML, ALICE_DOMAIN)
        self.assertEqual(result_alice_update.case.dynamic_case_properties()['plan_to_buy_gun'], 'no')


@use_sql_backend
class DomainTestSQL(DomainTest):
    pass
