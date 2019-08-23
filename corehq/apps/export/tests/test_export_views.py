# encoding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
import json
import os
from io import BytesIO
import datetime

from botocore.response import StreamingBody
from django.test import TestCase
from django.urls import reverse
from mock import patch

from corehq.apps.export.models import CaseExportInstance
from corehq.apps.export.models.new import DataFile
from corehq.apps.users.models import WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.export.dbaccessors import (
    delete_all_export_instances,
    get_form_exports_by_domain,
    get_case_exports_by_domain,
)
from corehq.apps.export.views.edit import (
    EditNewCustomCaseExportView,
    EditNewCustomFormExportView,
)
from corehq.apps.export.views.list import (
    DailySavedExportListView,
)
from corehq.apps.export.views.new import (
    CreateNewCustomCaseExportView,
    CreateNewCustomFormExportView,
    CreateNewDailySavedCaseExport,
)
from corehq.apps.export.views.utils import DataFileDownloadDetail
from corehq.util.test_utils import flag_enabled, generate_cases
from io import open


class FakeDB(object):

    def __init__(self, blobs):
        self.blobs = blobs

    def get(self, blob_id):
        content = self.blobs[blob_id]
        return StreamingBody(BytesIO(content), len(content))

    def delete(self, blob_id):
        pass


class ViewTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super(ViewTestCase, cls).setUpClass()
        cls.domain = Domain(name="donkeykong", is_active=True)
        cls.domain.save()

        cls.username = 'bananafana'
        cls.password = '*******'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password)
        cls.user.set_role(cls.domain.name, 'admin')
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain.delete()
        super(ViewTestCase, cls).tearDownClass()

    def setUp(self):
        self.client.login(username=self.username, password=self.password)


class DataFileDownloadDetailTest(ViewTestCase):

    @classmethod
    def setUpClass(cls):
        super(DataFileDownloadDetailTest, cls).setUpClass()
        with open(os.path.abspath(__file__), 'rb') as f:
            cls.content = f.read()
            f.seek(0)
            cls.data_file = DataFile.save_blob(
                f,
                domain=cls.domain.name,
                filename='foo.txt',
                description='all of the foo',
                content_type='text/plain',
                delete_after=datetime.datetime.utcnow() + datetime.timedelta(days=3)
            )

    @classmethod
    def tearDownClass(cls):
        super(DataFileDownloadDetailTest, cls).tearDownClass()
        cls.data_file.delete()

    def setUp(self):
        super(DataFileDownloadDetailTest, self).setUp()
        self.data_file_url = reverse(DataFileDownloadDetail.urlname, kwargs={
            'domain': self.domain.name, 'pk': self.data_file.id, 'filename': 'foo.txt'
        })

    @flag_enabled('DATA_FILE_DOWNLOAD')
    def test_data_file_download(self):
        try:
            resp = self.client.get(self.data_file_url)
        except TypeError as err:
            self.fail('Getting a data file raised a TypeError: {}'.format(err))
        self.assertEqual(resp.getvalue(), self.content)

    @flag_enabled('DATA_FILE_DOWNLOAD')
    def test_data_file_download_expired(self):
        self.data_file._meta.expires_on = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        self.data_file._meta.save()
        resp = self.client.get(self.data_file_url)
        self.assertEqual(resp.status_code, 404)


@generate_cases([
    (0, 999),
    (1000, 1999),
    (12000, None)
], DataFileDownloadDetailTest)
@flag_enabled('DATA_FILE_DOWNLOAD')
def test_data_file_download_partial(self, start, end):
    content_length = len(self.content)
    if end:
        range = '{}-{}'.format(start, end)
    else:
        range = '{}-'.format(start)

    resp = self.client.get(self.data_file_url, HTTP_RANGE='bytes={}'.format(range))
    self.assertEqual(resp.status_code, 206)
    expected_range_header = 'bytes {}-{}/{}'.format(start, end or (content_length - 1), content_length)
    self.assertEqual(resp['Content-Range'], expected_range_header)
    if end:
        expected_content = self.content[start:end + 1]
    else:
        expected_content = self.content[start:]

    self.assertEqual(resp['Content-Length'], '{}'.format(len(expected_content)))
    self.assertEqual(resp.getvalue(), expected_content)


class ExportViewTest(ViewTestCase):

    def tearDown(self):
        delete_all_export_instances()

    def test_create_form_export(self):
        resp = self.client.get(
            reverse(CreateNewCustomFormExportView.urlname, args=[self.domain.name]),
            {'export_tag': 'my_sweet_xmlns', 'app_id': 'r2d2'}
        )
        self.assertEqual(resp.status_code, 200)

    def test_create_case_export(self):
        resp = self.client.get(
            reverse(CreateNewCustomCaseExportView.urlname, args=[self.domain.name]),
            {'export_tag': 'random_case'}
        )
        self.assertEqual(resp.status_code, 200)

    def test_commit_form_export(self):
        export_post_data = json.dumps({
            "doc_type": "FormExportInstance",
            "domain": self.domain.name,
            "xmlns": "http://openrosa.org/formdesigner/237B85C0-78B1-4034-8277-5D37E3EA7FD1",
            "last_updated": None,
            "legacy_saved_export_schema_id": None,
            "is_daily_saved_export": False,
            "tables": [],
            "transform_dates": True,
            "last_accessed": None,
            "app_id": "6a48b8838d06febeeabb28c8c9516ab6",
            "is_deidentified": False,
            "split_multiselects": False,
            "external_blobs": {},
            "export_format": "csv",
            "include_errors": False,
            "type": "form",
            "name": "A Villager's Health > Registrationaa > Reg form: 2016-06-27"
        })
        resp = self.client.post(
            reverse(CreateNewCustomFormExportView.urlname, args=[self.domain.name]),
            export_post_data,
            content_type="application/json",
            follow=True
        )
        self.assertEqual(resp.status_code, 200)
        exports = get_form_exports_by_domain(self.domain.name)
        self.assertEqual(len(exports), 1)
        export = exports[0]

        resp = self.client.post(
            reverse(
                EditNewCustomFormExportView.urlname,
                args=[self.domain.name, export._id]
            ),
            export_post_data,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_edit_case_export(self):
        export_post_data = json.dumps({
            "doc_type": "CaseExportInstance",
            "domain": self.domain.name,
            "xmlns": "http://openrosa.org/formdesigner/237B85C0-78B1-4034-8277-5D37E3EA7FD1",
            "last_updated": None,
            "legacy_saved_export_schema_id": None,
            "is_daily_saved_export": False,
            "tables": [],
            "transform_dates": True,
            "last_accessed": None,
            "app_id": "6a48b8838d06febeeabb28c8c9516ab6",
            "is_deidentified": False,
            "split_multiselects": False,
            "external_blobs": {},
            "export_format": "csv",
            "include_errors": False,
            "type": "form",
            "name": "A Villager's Health > Registrationaa > Reg form: 2016-06-27"
        })
        resp = self.client.post(
            reverse(CreateNewCustomCaseExportView.urlname, args=[self.domain.name]),
            export_post_data,
            content_type="application/json",
            follow=True
        )
        self.assertEqual(resp.status_code, 200)

        exports = get_case_exports_by_domain(self.domain.name)
        self.assertEqual(len(exports), 1)
        export = exports[0]

        resp = self.client.post(
            reverse(
                EditNewCustomCaseExportView.urlname,
                args=[self.domain.name, export._id]
            ),
            export_post_data,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

    @patch('corehq.apps.export.views.list.domain_has_privilege', lambda x, y: True)
    @patch('corehq.apps.export.views.new.domain_has_privilege', lambda x, y: True)
    @patch('corehq.apps.export.views.utils.domain_has_privilege', lambda x, y: True)
    @patch('corehq.apps.accounting.utils.domain_has_privilege', lambda x, y: True)
    @patch("corehq.apps.export.tasks.rebuild_export")
    def test_edit_daily_saved_export_filters(self, _):
        # Create an export
        # Update the filters
        # confirm that the filters on the export have been updated appropriately

        export_post_data = json.dumps({
            "doc_type": "CaseExportInstance",
            "domain": self.domain.name,
            "xmlns": "http://openrosa.org/formdesigner/237B85C0-78B1-4034-8277-5D37E3EA7FD1",
            "last_updated": None,
            "legacy_saved_export_schema_id": None,
            "is_daily_saved_export": True,
            "tables": [],
            "transform_dates": True,
            "last_accessed": None,
            "app_id": "6a48b8838d06febeeabb28c8c9516ab6",
            "is_deidentified": False,
            "split_multiselects": False,
            "external_blobs": {},
            "export_format": "csv",
            "include_errors": False,
            "type": "case",
            "name": "A Villager's Health > Registrationaa > Reg form: 2016-06-27"
        })
        resp = self.client.post(
            reverse(CreateNewDailySavedCaseExport.urlname, args=[self.domain.name]),
            export_post_data,
            content_type="application/json",
            follow=True
        )
        self.assertEqual(resp.status_code, 200)

        exports = get_case_exports_by_domain(self.domain.name)
        self.assertEqual(len(exports), 1)
        export = exports[0]

        filter_form_data = {
            "emwf_case_filter": [],
            "date_range": "range",
            "start_date": "1992-01-30",
            "end_date": "2016-10-01",
        }

        resp = self.client.post(
            reverse('commit_filters', args=[self.domain.name]),
            {
                "export_id": export._id,
                "model_type": "case",
                "form_data": json.dumps(filter_form_data),
            },
        )
        self.assertEqual(resp.status_code, 200)
        response_content = json.loads(resp.content)
        self.assertFalse("error" in response_content, response_content.get("error"))
        export = CaseExportInstance.get(export._id)
        self.assertEqual(export.filters.date_period.period_type, 'range')

    def test_wrong_domain_save(self):
        export_post_data = json.dumps({
            "doc_type": "CaseExportInstance",
            "domain": 'wrong-domain',
            "xmlns": "http://openrosa.org/formdesigner/237B85C0-78B1-4034-8277-5D37E3EA7FD1",
            "last_updated": None,
            "legacy_saved_export_schema_id": None,
            "is_daily_saved_export": False,
            "tables": [],
            "transform_dates": True,
            "last_accessed": None,
            "app_id": "6a48b8838d06febeeabb28c8c9516ab6",
            "is_deidentified": False,
            "split_multiselects": False,
            "external_blobs": {},
            "export_format": "csv",
            "include_errors": False,
            "type": "form",
            "name": "A Villager's Health > Registrationaa > Reg form: 2016-06-27"
        })
        resp = self.client.post(
            reverse(CreateNewCustomCaseExportView.urlname, args=[self.domain.name]),
            export_post_data,
            content_type="application/json",
            follow=True
        )
        self.assertEqual(resp.status_code, 500)  # This is an ajax call which handles the 500
