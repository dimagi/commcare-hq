from __future__ import print_function
from __future__ import absolute_import
from StringIO import StringIO
import json
import datetime

import mock
from django.urls import reverse
from django.test import TestCase, SimpleTestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.export.models import FormExportInstance, TableConfiguration, ExportColumn, ScalarItem, PathNode
from corehq.apps.reports.models import FormExportSchema
from corehq.apps.reports.tasks import (
    _extract_form_attachment_info,
    _get_export_properties,
)
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import XFormInstanceSQL, XFormAttachmentSQL
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
        <n1:userID>{user_id}</n1:userID>
        <n1:instanceID>{xform_id}</n1:instanceID>
        <n2:appVersion xmlns:n2="http://commcarehq.org/xforms">2.0</n2:appVersion>
    </n1:meta>
</data>
"""


class FormMultimediaExportTest(SimpleTestCase):

    def test_get_export_properties(self):
        export_instance = FormExportInstance(
            tables=[
                TableConfiguration(
                    label="My table",
                    selected=True,
                    path=[],
                    columns=[
                        ExportColumn(
                            label="Q3",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='q3')],
                            ),
                            selected=True,
                        ),
                        ExportColumn(
                            label="dontshow",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='dontshow')],
                            ),
                            selected=False,
                        ),
                    ]
                ),
                TableConfiguration(
                    label="My other table",
                    selected=True,
                    path=[PathNode(name='form', is_repeat=False), PathNode(name="q2", is_repeat=False)],
                    columns=[
                        ExportColumn(
                            label="Q4",
                            item=ScalarItem(
                                path=[PathNode(name='form'), PathNode(name='q2'), PathNode(name='q4')],
                            ),
                            selected=True,
                        ),
                    ]
                )
            ]
        )
        with mock.patch('corehq.apps.export.models.new.FormExportInstance.get', return_value=export_instance):
            props = _get_export_properties("fake id for my export instance", False)
            self.assertEqual(props, set(['q2-q4', 'q3']))

    def test_extract_form_attachment_info(self):
        image_1_name = "1234.jpg"
        image_2_name = "5678.jpg"
        form = {
            "name": "foo",
            "color": "bar",
            "image_1": image_1_name,
            "my_group": {
                "image_2": image_2_name
            }
        }
        attachments = {
            image_1_name: {
                "content_type": "image/jpeg",
                "content_length": 1024,
            },
            image_2_name: {
                "content_type": "image/jpeg",
                "content_length": 2048,
            },
            "form.xml": {
                "content_type": "text/xml",
                "content_length": 2048,
            }
        }
        with mock.patch.object(XFormInstanceSQL, 'form_data') as form_data_mock:
            form_data_mock.__get__ = mock.MagicMock(return_value=form)
            couch_xform = XFormInstance(
                received_on=datetime.datetime.now(),
                form=form,
            )
            for name, meta in attachments.items():
                couch_xform.deferred_put_attachment("content", name, **meta)
            sql_xform = XFormInstanceSQL(received_on=datetime.datetime.now())
            sql_xform.unsaved_attachments = [XFormAttachmentSQL(name=name, **meta)
                for name, meta in attachments.items()]

            for xform in (couch_xform, sql_xform):
                print(type(xform).__name__)
                form_info = _extract_form_attachment_info(xform, {"my_group-image_2", "image_1"})
                attachments = {a['name']: a for a in form_info['attachments']}
                self.assertTrue(image_1_name in attachments)
                self.assertTrue(image_2_name in attachments)
                self.assertEqual(attachments[image_1_name]['question_id'], "image_1")
                self.assertEqual(attachments[image_2_name]['question_id'], "my_group-image_2")


class FormExportTest(TestCase):

    def setUp(self):
        super(FormExportTest, self).setUp()
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
        super(FormExportTest, self).tearDown()

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
