from StringIO import StringIO
import json
from django.core.urlresolvers import reverse
from django.utils.unittest.case import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.models import FormExportSchema
from corehq.apps.users.models import CommCareUser
from couchexport.models import Format
from couchforms.models import XFormInstance
from django_digest.test import Client

XMLNS = 'http://www.commcarehq.org/example/hello-world'
XFORM_ID = '50fa6deb-91f3-4f9b-9d4c-f5ed312457fa'

XML_DATA = """<?xml version='1.0' ?>
<data uiVersion="1" version="63" name="Hello World" xmlns:jrm="http://dev.commcarehq.org/jr/xforms" xmlns="{xmlns}">
    <name>S</name>
    <color>1</color>
    <date>2012-10-02</date>
    <n1:meta xmlns:n1="http://openrosa.org/jr/xforms">
        <n1:deviceID>cloudcare</n1:deviceID>
        <n1:timeStart>2012-10-15T15:26:02.386-04</n1:timeStart>
        <n1:timeEnd>2012-10-15T15:26:14.745-04</n1:timeEnd>
        <n1:username>user1</n1:username>
        <n1:userID>9247d96f8d6496f51cda6bf2bab963a7</n1:userID>
        <n1:instanceID>{xform_id}</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">2.0</n2:appVersion>
    </n1:meta>
</data>
""".format(xmlns=XMLNS, xform_id=XFORM_ID)


class FormExportTest(TestCase):
    def setUp(self):
        self.app_id = 'kasdlfkjsldfkjsdlkjf'
        self.domain_name = 'form-export-test'
        self.domain = create_domain(self.domain_name)
        self.username = 'danny'
        self.couch_user = CommCareUser.create(self.domain_name, self.username,
                                              password='xxx')
        self.couch_user.save()
        self.client = Client()
        self.client.login(username=self.couch_user.username, password='xxx')
        self.url = reverse("receiver_post_with_app_id",
                           args=[self.domain_name, self.app_id])

        def post_it():
            f = StringIO(XML_DATA)
            f.name = 'form.xml'
            response = self.client.post(self.url, {'xml_submission_file': f})
        self.form1 = post_it()
        self.form2 = post_it()

        self.custom_export = FormExportSchema.wrap({
            'type': 'form',
            'app_id': self.app_id,
            'default_format': Format.JSON,
            'index': json.dumps([self.domain_name, XMLNS]),
            'tables': [{
                'index': '#',
                'display': 'Export',
                'columns': [{'index': 'form.name', 'display': 'Name'}],
            }]
        })

    def test_include_duplicates(self):

        self.custom_export.include_errors = True
        tmp, _ = self.custom_export.get_export_files()
        data = tmp.getvalue()
        data = json.loads(data)
        self.assertEqual(data['Export']['headers'], ['Name'])
        self.assertEqual(len(data['Export']['rows']), 2)

        self.custom_export.include_errors = False
        tmp, _ = self.custom_export.get_export_files()
        data = tmp.getvalue()
        data = json.loads(data)
        self.assertEqual(data['Export']['headers'], ['Name'])
        self.assertEqual(len(data['Export']['rows']), 1)