import json
from collections import namedtuple

from django.core.urlresolvers import reverse
from django.test.testcases import TestCase
from tastypie.models import ApiKey

from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, SoftwarePlanEdition, Subscription
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.domain.models import Domain
from corehq.apps.repeaters.models import FormRepeater
from corehq.apps.users.models import WebUser
from corehq.apps.zapier import consts
from corehq.apps.zapier.models import ZapierSubscription

from corehq.apps.accounting.tests import generator

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
MockResponse = namedtuple('MockResponse', 'status_code reason')


class TestZapierIntegration(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestZapierIntegration, cls).setUpClass()
        generator.instantiate_accounting()

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
        super(TestZapierIntegration, cls).tearDownClass()

    def tearDown(self):
        ZapierSubscription.objects.all().delete()

    def test_subscribe(self):
        data = {
            "subscription_url": ZAPIER_URL,
            "target_url": ZAPIER_URL,
            "event": consts.EventTypes.NEW_FORM,
            "application": self.application.get_id,
            "form": FORM_XMLNS
        }
        response = self.client.post(reverse('zapier_subscribe', kwargs={'domain': self.domain}),
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

    def test_unsubscribe(self):
        ZapierSubscription.objects.create(
            url=ZAPIER_URL,
            user_id=self.web_user.get_id,
            domain=TEST_DOMAIN,
            event_name=consts.EventTypes.NEW_FORM,
            application_id=self.application.get_id,
            form_xmlns=FORM_XMLNS
        )
        data = {
            "subscription_url": ZAPIER_URL,
            "target_url": ZAPIER_URL
        }
        response = self.client.post(reverse('zapier_unsubscribe', kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ZapierSubscription.objects.all().count(), 0)
        self.assertEqual(len(FormRepeater.by_domain(TEST_DOMAIN)), 0)

    def test_urls_conflict(self):
        data = {
            "subscription_url": ZAPIER_URL,
            "target_url": ZAPIER_URL,
            "event": consts.EventTypes.NEW_FORM,
            "application": self.application.get_id,
            "form": FORM_XMLNS
        }
        response = self.client.post(reverse('zapier_subscribe', kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('zapier_subscribe', kwargs={'domain': self.domain}),
                                    data=json.dumps(data),
                                    content_type='application/json; charset=utf-8',
                                    HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 409)
