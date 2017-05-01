import json
from collections import namedtuple

from django.urls import reverse
from django.test.testcases import TestCase, SimpleTestCase
from django.test.client import Client

from tastypie.models import ApiKey
from tastypie.resources import Resource

from casexml.apps.case.mock import CaseFactory

from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, SoftwarePlanEdition, Subscription
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.domain.models import Domain
from corehq.apps.repeaters.models import FormRepeater, CaseRepeater
from corehq.apps.users.models import WebUser
from corehq.apps.zapier.consts import EventTypes
from corehq.apps.zapier.views import SubscribeView, UnsubscribeView, ZapierCreateCase, ZapierUpdateCase
from corehq.apps.zapier.api.v0_5 import ZapierCustomFieldCaseResource
from corehq.apps.zapier.models import ZapierSubscription

from corehq.apps.zapier.util import remove_advanced_fields
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils

XFORM = """
    <h:html xmlns:h="http://www.w3.org/1999/xhtml" xmlns:orx="http://openrosa.org/jr/xforms"
    xmlns="http://www.w3.org/2002/xforms" xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:jr="http://openrosa.org/javarosa" xmlns:vellum="http://commcarehq.org/xforms/vellum">
        <h:head>
            <h:title>Checkup</h:title>
            <model>
                <instance>
                    <data xmlns:jrm="http://dev.commcarehq.org/jr/xforms"
                    xmlns="https://www.commcarehq.org/test/zapier/"
                    uiVersion="1" version="1" name="Checkup">
                        <question1/>
                        <question2/>
                        <stub/>
                    </data>
                </instance>
                <bind nodeset="/data/question1" type="xsd:string"/>
                <bind nodeset="/data/question2" type="xsd:string"/>
                <itext>
                    <translation lang="en" default="">
                        <text id="question1-label">
                            <value>question1</value>
                        </text>
                        <text id="question2-label">
                            <value>question2</value>
                        </text>
                    </translation>
                </itext>
            </model>
        </h:head>
        <h:body>
            <input ref="/data/question1">
                <label ref="jr:itext('question1-label')"/>
            </input>
            <input ref="/data/question2">
                <label ref="jr:itext('question2-label')"/>
            </input>
        </h:body>
    </h:html>
"""

FORM_XMLNS = "https://www.commcarehq.org/test/zapier/"
CASE_TYPE = "lemon-meringue-pie"
XFORM_XML_TEMPLATE = """<?xml version='1.0' ?>
<data xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="%s">
    <woman_name>Alpha</woman_name>
    <husband_name>Beta</husband_name>
    <meta>
        <deviceID>O2XLT0WZW97W1A91E2W1Y0NJG</deviceID>
        <timeStart>2011-10-01T15:25:18.404-04</timeStart>
        <timeEnd>2011-10-01T15:26:29.551-04</timeEnd>
        <username>admin</username>
        <userID>{}</userID>
        <instanceID>{}</instanceID>
    </meta>
</data>
""" % FORM_XMLNS
ZAPIER_URL = "https://zapier.com/hooks/standard/1387607/5ccf35a5a1944fc9bfdd2c94c28c9885/"
TEST_DOMAIN = 'test-domain'
BAD_EVENT_NAME = 'lemon_meringue_pie'
MockResponse = namedtuple('MockResponse', 'status_code reason')


class TestZapierIntegration(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestZapierIntegration, cls).setUpClass()

        cls.domain_object = Domain.get_or_create_with_name(TEST_DOMAIN, is_active=True)
        cls.domain = cls.domain_object.name

        account = BillingAccount.get_or_create_account_by_domain(cls.domain, created_by="automated-test")[0]
        plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.STANDARD)
        subscription = Subscription.new_domain_subscription(account, cls.domain, plan)
        subscription.is_active = True
        subscription.save()

        cls.web_user = WebUser.create(cls.domain, 'test', '******')
        api_key_object, _ = ApiKey.objects.get_or_create(user=cls.web_user.get_django_user())
        cls.api_key = api_key_object.key
        cls.application = Application.new_app(cls.domain, 'Test App')
        cls.application.save()
        module = cls.application.add_module(Module.new_module("Module 1", "en"))
        cls.application.new_form(module.id, name="Form1", attachment=XFORM, lang="en")
        cls.application.save()

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete()
        cls.application.delete()
        cls.domain_object.delete()
        for repeater in FormRepeater.by_domain(cls.domain):
            repeater.delete()
        for repeater in CaseRepeater.by_domain(cls.domain):
            repeater.delete()
        super(TestZapierIntegration, cls).tearDownClass()

    def tearDown(self):
        ZapierSubscription.objects.all().delete()

    def test_subscribe_form(self):
        data = {
            "subscription_url": ZAPIER_URL,
            "target_url": ZAPIER_URL,
            "event": EventTypes.NEW_FORM,
            "application": self.application.get_id,
            "form": FORM_XMLNS
        }
        response = self.client.post(reverse(SubscribeView.urlname, kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
        self.assertEqual(response.status_code, 200)

        subscription = ZapierSubscription.objects.get(
            url=ZAPIER_URL
        )
        self.assertListEqual(
            [subscription.url, subscription.user_id, subscription.domain, subscription.form_xmlns],
            [ZAPIER_URL, self.web_user.get_id, TEST_DOMAIN, FORM_XMLNS]
        )
        self.assertIsNotNone(subscription.repeater_id)
        self.assertNotEqual(subscription.repeater_id, '')

    def test_subscribe_case(self):
        data = {
            "subscription_url": ZAPIER_URL,
            "target_url": ZAPIER_URL,
            "event": EventTypes.NEW_CASE,
            "case_type": CASE_TYPE
        }
        response = self.client.post(reverse(SubscribeView.urlname, kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
        self.assertEqual(response.status_code, 200)

        subscription = ZapierSubscription.objects.get(
            url=ZAPIER_URL
        )
        self.assertListEqual(
            [subscription.url, subscription.user_id, subscription.domain, subscription.case_type],
            [ZAPIER_URL, self.web_user.get_id, TEST_DOMAIN, CASE_TYPE]
        )
        self.assertIsNotNone(subscription.repeater_id)
        self.assertNotEqual(subscription.repeater_id, '')

    def test_subscribe_error(self):
        data = {
            "subscription_url": ZAPIER_URL,
            "target_url": ZAPIER_URL,
            "event": BAD_EVENT_NAME,
            "case_type": CASE_TYPE
        }
        response = self.client.post(reverse(SubscribeView.urlname, kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
        self.assertEqual(response.status_code, 400)

    def test_unsubscribe_form(self):
        ZapierSubscription.objects.create(
            url=ZAPIER_URL,
            user_id=self.web_user.get_id,
            domain=TEST_DOMAIN,
            event_name=EventTypes.NEW_FORM,
            application_id=self.application.get_id,
            form_xmlns=FORM_XMLNS
        )
        data = {
            "subscription_url": ZAPIER_URL,
            "target_url": ZAPIER_URL
        }
        response = self.client.post(reverse(UnsubscribeView.urlname, kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ZapierSubscription.objects.all().count(), 0)
        self.assertEqual(len(FormRepeater.by_domain(TEST_DOMAIN)), 0)

    def test_unsubscribe_case(self):
        ZapierSubscription.objects.create(
            url=ZAPIER_URL,
            user_id=self.web_user.get_id,
            domain=TEST_DOMAIN,
            event_name=EventTypes.NEW_CASE,
            application_id=self.application.get_id,
            case_type=CASE_TYPE,
        )
        data = {
            "subscription_url": ZAPIER_URL,
            "target_url": ZAPIER_URL
        }
        response = self.client.post(reverse(UnsubscribeView.urlname, kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ZapierSubscription.objects.all().count(), 0)
        self.assertEqual(len(CaseRepeater.by_domain(TEST_DOMAIN)), 0)

    def test_urls_conflict(self):
        data = {
            "subscription_url": ZAPIER_URL,
            "target_url": ZAPIER_URL,
            "event": EventTypes.NEW_FORM,
            "application": self.application.get_id,
            "form": FORM_XMLNS
        }
        response = self.client.post(reverse(SubscribeView.urlname, kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse(SubscribeView.urlname, kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 409)


class TestRemoveAdvancedFields(SimpleTestCase):

    def test_form(self):
        form = {
            "build_id": "de9553b384b1ff3acaceaed4a217f277",
            "domain": "test",
            "form": {
                "#type": "data",
                "@name": "Test",
                "@uiVersion": "1",
                "@version": "6",
                "@xmlns": "http://openrosa.org/formdesigner/test",
                "age": "3.052703627652293",
                "case": {
                    "@case_id": "67dfe2a9-9413-4811-b5f5-a7c841085e9e",
                    "@date_modified": "2016-12-20T12:13:23.870000Z",
                    "@user_id": "cff3d2fb45eafd1abbc595ae89f736a6",
                    "@xmlns": "http://commcarehq.org/case/transaction/v2",
                    "update": {
                        "test": ""
                    }
                },
                "dob": "2013-12-01",
                "dose_counter": "0",
                "follow_up_test_date": "",
                "follow_up_test_type": "",
                "grp_archive_person": {
                    "archive_person": {
                        "case": {
                            "@case_id": "d2fcfa48-5286-4623-a209-6a9c30781b3d",
                            "@date_modified": "2016-12-20T12:13:23.870000Z",
                            "@user_id": "cff3d2fb45eafd1abbc595ae89f736a6",
                            "@xmlns": "http://commcarehq.org/case/transaction/v2",
                            "update": {
                                "archive_reason": "not_evaluated",
                                "owner_id": "_archive_"
                            }
                        }
                    },
                    "close_episode": {
                        "case": {
                            "@case_id": "67dfe2a9-9413-4811-b5f5-a7c841085e9e",
                            "@date_modified": "2016-12-20T12:13:23.870000Z",
                            "@user_id": "cff3d2fb45eafd1abbc595ae89f736a6",
                            "@xmlns": "http://commcarehq.org/case/transaction/v2",
                            "close": ""
                        }
                    },
                    "close_occurrence": {
                        "case": {
                            "@case_id": "912d0ec6-709f-4d82-81d8-6a5aa163e2fb",
                            "@date_modified": "2016-12-20T12:13:23.870000Z",
                            "@user_id": "cff3d2fb45eafd1abbc595ae89f736a6",
                            "@xmlns": "http://commcarehq.org/case/transaction/v2",
                            "close": ""
                        }
                    },
                    "close_referrals": {
                        "@count": "0",
                        "@current_index": "0",
                        "@ids": ""
                    }
                },
                "lbl_form_end": "OK",
                "length_of_cp": "",
                "length_of_ip": "",
                "meta": {
                    "@xmlns": "http://openrosa.org/jr/xforms",
                    "appVersion": "CommCare Android, version \"2.31.0\"(423345). "
                                  "App v59. CommCare Version 2.31. Build 423345, built on: 2016-11-02",
                    "app_build_version": 59,
                    "commcare_version": "2.31.0",
                    "deviceID": "359872069029881",
                    "geo_point": None,
                    "instanceID": "2d0e138e-c9b0-4998-a7fb-06b7109e0bf7",
                    "location": {
                        "#text": "54.4930116 18.5387613 0.0 21.56",
                        "@xmlns": "http://commcarehq.org/xforms"
                    },
                    "timeEnd": "2016-12-20T12:13:23.870000Z",
                    "timeStart": "2016-12-20T12:13:08.346000Z",
                    "userID": "cff3d2fb45eafd1abbc595ae89f736a6",
                    "username": "test"
                },
            }
        }
        remove_advanced_fields(form_dict=form)
        self.assertIsNone(form['form']['meta'].get('userID'))
        self.assertIsNone(form.get('xmlns'))
        self.assertIsNone(form['form'].get('@name'))
        self.assertIsNone(form['form']['meta'].get('appVersion'))
        self.assertIsNone(form['form']['meta'].get('deviceID'))
        self.assertIsNone(form['form']['meta'].get('location'))
        self.assertIsNone(form.get('app_id'))
        self.assertIsNone(form.get('build_id'))
        self.assertIsNone(form['form'].get('@version'))
        self.assertIsNone(form.get('doc_type'))
        self.assertIsNone(form.get('last_sync_token'))
        self.assertIsNone(form.get('partial_submission'))

        self.assertIsNotNone(form['domain'])


class TestZapierCustomFields(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestZapierCustomFields, cls).setUpClass()
        cls.test_url = "http://commcarehq.org/?domain=joto&case_type=teddiursa"

    def test_case_fields(self):

        expected_fields = [
            {"help_text": "", "key": "properties__level", "label": "Level", "type": "unicode"},
            {"help_text": "", "key": "properties__mood", "label": "Mood", "type": "unicode"},
            {"help_text": "", "key": "properties__move_type", "label": "Move type", "type": "unicode"},
            {"help_text": "", "key": "properties__name", "label": "Name", "type": "unicode"},
            {"help_text": "", "key": "properties__opened_on", "label": "Opened on", "type": "unicode"},
            {"help_text": "", "key": "properties__owner_id", "label": "Owner id", "type": "unicode"},
            {"help_text": "", "key": "properties__prop1", "label": "Prop1", "type": "unicode"},
            {"help_text": "", "key": "properties__type", "label": "Type", "type": "unicode"},
            {"help_text": "", "key": "date_closed", "label": "Date closed", "type": "unicode"},
            {"help_text": "", "key": "xform_ids", "label": "XForm IDs", "type": "unicode"},
            {"help_text": "", "key": "properties__date_opened", "label": "Date opened", "type": "unicode"},
            {"help_text": "", "key": "properties__external_id", "label": "External ID", "type": "unicode"},
            {"help_text": "", "key": "properties__case_name", "label": "Case name", "type": "unicode"},
            {"help_text": "", "key": "properties__case_type", "label": "Case type", "type": "unicode"},
            {"help_text": "", "key": "user_id", "label": "User ID", "type": "unicode"},
            {"help_text": "", "key": "date_modified", "label": "Date modified", "type": "unicode"},
            {"help_text": "", "key": "case_id", "label": "Case ID", "type": "unicode"},
            {"help_text": "", "key": "properties__owner_id", "label": "Owner ID", "type": "unicode"},
            {"help_text": "", "key": "resource_uri", "label": "Resource URI", "type": "unicode"}
        ]

        request = Client().get(self.test_url).wsgi_request
        bundle = Resource().build_bundle(data={}, request=request)

        factory = CaseFactory(domain="joto")
        factory.create_case(
            case_type='teddiursa',
            owner_id='owner1',
            case_name='dre',
            update={'prop1': 'blah', 'move_type': 'scratch', 'mood': 'happy', 'level': '100'}
        )

        actual_fields = ZapierCustomFieldCaseResource().obj_get_list(bundle)
        for i in range(len(actual_fields)):
            self.assertEqual(expected_fields[i], actual_fields[i].get_content())


class TestZapierCreateCaseAction(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestZapierCreateCaseAction, cls).setUpClass()
        cls.domain_object = Domain.get_or_create_with_name('fruit', is_active=True)
        cls.domain = cls.domain_object.name
        account = BillingAccount.get_or_create_account_by_domain(cls.domain, created_by="automated-test")[0]
        plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.STANDARD)
        subscription = Subscription.new_domain_subscription(account, cls.domain, plan)
        subscription.is_active = True
        subscription.save()
        cls.query_string = "?domain=fruit&case_type=watermelon&owner_id=test_user&user=test"
        cls.data = {'case_name': 'test1', 'price': '11'}
        cls.accessor = CaseAccessors(cls.domain)
        cls.user = WebUser.create(cls.domain, 'test', '******')
        api_key_object, _ = ApiKey.objects.get_or_create(user=cls.user.get_django_user())
        cls.api_key = api_key_object.key

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain_object.delete()
        FormProcessorTestUtils.delete_all_cases()
        super(TestZapierCreateCaseAction, cls).tearDownClass()

    def test_create_case(self):
        response = self.client.post(reverse(ZapierCreateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(self.data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 200)

        case_id = self.accessor.get_case_ids_in_domain()
        case = self.accessor.get_case(case_id[0])
        self.assertEqual('test1', case.get_case_property('name'))
        self.assertEqual('11', case.get_case_property('price'))
        self.assertEqual('watermelon', case.get_case_property('type'))

    def test_update_case(self):
        response = self.client.post(reverse(ZapierCreateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(self.data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 200)
        case_id = self.accessor.get_case_ids_in_domain()
        case = self.accessor.get_case(case_id[0])
        self.assertEqual('11', case.get_case_property('price'))

        data = {'case_name': 'test1', 'price': '15', 'case_id': case_id[0]}
        response = self.client.post(reverse(ZapierUpdateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 200)
        case = self.accessor.get_case(case_id[0])
        self.assertEqual('15', case.get_case_property('price'))

    def test_update_case_does_not_exist(self):
        data = {'case_name': 'test1', 'price': '15', 'case_id': 'fake_id'}
        response = self.client.post(reverse(ZapierUpdateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 403)

    def test_update_case_wrong_domain(self):
        response = self.client.post(reverse(ZapierCreateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(self.data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 200)
        case_id = self.accessor.get_case_ids_in_domain()

        data = {'case_name': 'test1', 'price': '15', 'case_id': case_id[0]}
        query_string = "?domain=me&case_type=watermelon&user_id=test_user&user=test"
        response = self.client.post(reverse(ZapierUpdateCase.urlname,
                                            kwargs={'domain': self.domain}) + query_string,
                               data=json.dumps(data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 403)

    def test_update_case_wrong_type(self):
        response = self.client.post(reverse(ZapierCreateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(self.data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 200)
        case_id = self.accessor.get_case_ids_in_domain()

        data = {'case_name': 'test1', 'price': '15', 'case_id': case_id[0]}
        query_string = "?domain=fruit&case_type=orange&user_id=test_user&user=test"
        response = self.client.post(reverse(ZapierUpdateCase.urlname,
                                            kwargs={'domain': self.domain}) + query_string,
                               data=json.dumps(data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 403)

    def test_user_does_not_have_access(self):
        fake_domain = Domain.get_or_create_with_name('fake', is_active=True)
        fake_user = WebUser.create('fake', 'faker2', '******')
        query_string = "?domain=fruit&case_type=fake&user_id=test_user&user=faker2"
        response = self.client.post(reverse(ZapierCreateCase.urlname,
                                            kwargs={'domain': self.domain}) + query_string,
                               data=json.dumps(self.data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 403)
        fake_domain.delete()
        fake_user.delete()
