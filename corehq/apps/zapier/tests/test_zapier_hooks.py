import json

from django.test.testcases import TestCase
from django.urls import reverse

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.zapier.consts import CASE_TYPE_REPEATER_CLASS_MAP, EventTypes
from corehq.apps.zapier.models import ZapierSubscription
from corehq.apps.zapier.tests.test_utils import bootrap_domain_for_zapier
from corehq.apps.zapier.views import SubscribeView, UnsubscribeView
from corehq.motech.repeaters.models import CreateCaseRepeater, FormRepeater

ZAPIER_URL = "https://zapier.com/hooks/standard/1387607/5ccf35a5a1944fc9bfdd2c94c28c9885/"
TEST_DOMAIN = 'test-domain'
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
BAD_EVENT_NAME = 'lemon_meringue_pie'


class TestZapierIntegration(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestZapierIntegration, cls).setUpClass()
        cls.domain = TEST_DOMAIN
        cls.domain_object, cls.web_user, cls.api_key = bootrap_domain_for_zapier(cls.domain)
        cls.application = Application.new_app(cls.domain, 'Test App')
        cls.application.save()
        module = cls.application.add_module(Module.new_module("Module 1", "en"))
        cls.application.new_form(module.id, name="Form1", attachment=XFORM, lang="en")
        cls.application.save()

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete(cls.domain, deleted_by=None)
        cls.application.delete()
        cls.domain_object.delete()
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
        self.assertEqual(subscription.id, response.json()['id'])
        self.assertListEqual(
            [subscription.url, subscription.user_id, subscription.domain, subscription.form_xmlns],
            [ZAPIER_URL, self.web_user.get_id, TEST_DOMAIN, FORM_XMLNS]
        )
        self.assertIsNotNone(subscription.repeater_id)
        self.assertNotEqual(subscription.repeater_id, '')

    def test_subscribe_case_events(self):
        for event, repeater_class in CASE_TYPE_REPEATER_CLASS_MAP.items():
            url = ZAPIER_URL + '/{}'.format(event)  # because urls must be unique
            data = {
                "subscription_url": ZAPIER_URL,
                "target_url": url,
                "event": event,
                "case_type": CASE_TYPE
            }
            response = self.client.post(reverse(SubscribeView.urlname, kwargs={'domain': self.domain}),
                                        data=json.dumps(data),
                                        content_type='application/json; charset=utf-8',
                                        HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
            self.assertEqual(response.status_code, 200)

            subscription = ZapierSubscription.objects.get(url=url)
            self.assertListEqual(
                [subscription.url, subscription.user_id, subscription.domain, subscription.case_type],
                [url, self.web_user.get_id, TEST_DOMAIN, CASE_TYPE]
            )
            self.assertIsNotNone(subscription.repeater_id)
            self.assertNotEqual(subscription.repeater_id, '')
            self.assertEqual(repeater_class.objects.get(id=subscription.repeater_id).repeater_type,
                             repeater_class._repeater_type)

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
        self.assertNotEqual(len(FormRepeater.objects.by_domain(TEST_DOMAIN)), 0)
        data = {
            "target_url": ZAPIER_URL
        }
        response = self.client.post(reverse(UnsubscribeView.urlname, kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ZapierSubscription.objects.all().count(), 0)
        self.assertEqual(len(FormRepeater.objects.by_domain(TEST_DOMAIN)), 0)

    def test_unsubscribe_case(self):
        ZapierSubscription.objects.create(
            url=ZAPIER_URL,
            user_id=self.web_user.get_id,
            domain=TEST_DOMAIN,
            event_name=EventTypes.NEW_CASE,
            application_id=self.application.get_id,
            case_type=CASE_TYPE,
        )
        self.assertNotEqual(len(CreateCaseRepeater.objects.by_domain(TEST_DOMAIN)), 0)
        data = {
            "target_url": ZAPIER_URL
        }
        response = self.client.post(reverse(UnsubscribeView.urlname, kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ZapierSubscription.objects.all().count(), 0)
        self.assertEqual(len(CreateCaseRepeater.objects.by_domain(TEST_DOMAIN)), 0)

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
