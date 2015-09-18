from StringIO import StringIO
import json
import os
from django.core.urlresolvers import reverse
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.reports.models import FormExportSchema
from corehq.apps.users.models import CommCareUser
from couchexport.models import Format
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
        <n1:userID>{user_id}</n1:userID>
        <n1:instanceID>{xform_id}</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">2.0</n2:appVersion>
    </n1:meta>
</data>
"""


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

    def tearDown(self):
        self.couch_user.delete()

    def post_it(self, user_id=None, form_id=XFORM_ID):
        user_id = user_id or self.couch_user._id
        f = StringIO(XML_DATA.format(
            user_id=user_id,
            xmlns=XMLNS,
            xform_id=form_id,
        ))
        f.name = 'form.xml'
        return self.client.post(self.url, {'xml_submission_file': f})

    def test_include_duplicates(self):
        self.post_it()
        self.post_it()

        self.custom_export.include_errors = True
        files = self.custom_export.get_export_files()
        data = json.loads(files.file.payload)
        self.assertEqual(data['Export']['headers'], ['Name'])
        self.assertEqual(len(data['Export']['rows']), 2)

        self.custom_export.include_errors = False
        files = self.custom_export.get_export_files()
        data = json.loads(files.file.payload)
        self.assertEqual(data['Export']['headers'], ['Name'])
        self.assertEqual(len(data['Export']['rows']), 1)

    def test_exclude_unknown_users(self):
        self.post_it(form_id='good', user_id=self.couch_user._id)
        files = self.custom_export.get_export_files()
        data = json.loads(files.file.payload)
        self.assertEqual(len(data['Export']['rows']), 1)

        # posting from a non-real user shouldn't update
        self.post_it(form_id='bad', user_id='notarealuser')
        files = self.custom_export.get_export_files()
        data = json.loads(files.file.payload)
        self.assertEqual(len(data['Export']['rows']), 1)

        # posting from the real user should update
        self.post_it(form_id='stillgood', user_id=self.couch_user._id)
        files = self.custom_export.get_export_files()
        data = json.loads(files.file.payload)
        self.assertEqual(len(data['Export']['rows']), 2)
