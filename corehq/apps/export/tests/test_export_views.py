import datetime
import json
import pytest
import os
from io import BytesIO
from unittest.mock import patch
from urllib.parse import urlencode

from django.http import HttpResponse
from django.test import TestCase
from django.urls import reverse

from botocore.response import StreamingBody
from couchdbkit.exceptions import ResourceNotFound

from corehq import privileges
from corehq.apps.domain.models import Domain
from corehq.apps.export.dbaccessors import (
    delete_all_export_instances,
    get_case_exports_by_domain,
    get_form_exports_by_domain,
)
from corehq.apps.export.models import CaseExportInstance, FormExportInstance
from corehq.apps.export.models.new import DataFile
from corehq.apps.export.views.edit import (
    EditNewCustomCaseExportView,
    EditNewCustomFormExportView,
)
from corehq.apps.export.views.new import (
    CreateNewCustomCaseExportView,
    CreateNewCustomFormExportView,
    CreateNewDailySavedCaseExport,
)
from corehq.apps.export.views.utils import DataFileDownloadDetail
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import generate_cases, privilege_enabled


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
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, None, None)
        cls.user.set_role(cls.domain.name, 'admin')
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super(ViewTestCase, cls).tearDownClass()

    def setUp(self):
        self.client.login(username=self.username, password=self.password)


@privilege_enabled(privileges.DATA_FILE_DOWNLOAD)
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

    def test_data_file_download(self):
        try:
            resp = self.client.get(self.data_file_url)
        except TypeError as err:
            self.fail('Getting a data file raised a TypeError: {}'.format(err))
        self.assertEqual(resp.getvalue(), self.content)

    def test_data_file_download_expired(self):
        self.data_file._meta.expires_on = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        self.data_file._meta.save()
        resp = self.client.get(self.data_file_url)
        self.assertEqual(resp.status_code, 404)


@generate_cases([
    (0, 999),
    (1000, 1999),
    (11000, None)  # This test uses this file (test_export_views.py). `11000` must be less than its size.
], DataFileDownloadDetailTest)
@privilege_enabled(privileges.DATA_FILE_DOWNLOAD)
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

    @patch("couchforms.analytics.get_form_count_breakdown_for_domain", lambda *a: {})
    def test_create_form_export(self):
        resp = self.client.get(
            reverse(CreateNewCustomFormExportView.urlname, args=[self.domain.name]),
            {'export_tag': 'my_sweet_xmlns', 'app_id': 'r2d2'}
        )
        self.assertEqual(resp.status_code, 200)

    @patch("corehq.apps.export.views.new.get_case_types_for_domain", lambda *a: ['random_case'])
    def test_create_case_export_with_invalid_case(self):
        resp = self.client.get(
            reverse(CreateNewCustomCaseExportView.urlname, args=[self.domain.name]),
            {'export_tag': 'some_case'}
        )
        self.assertEqual(resp.status_code, 302)

    @patch("corehq.apps.export.views.new.get_case_types_for_domain", lambda *a: ['random_case'])
    def test_create_case_export(self):
        resp = self.client.get(
            reverse(CreateNewCustomCaseExportView.urlname, args=[self.domain.name]),
            {'export_tag': 'random_case'}
        )
        self.assertEqual(resp.status_code, 200)

    @patch("corehq.apps.export.views.new.get_case_types_for_domain", lambda *a: ['random_case'])
    def test_no_access_outside_of_domain(self):
        export = CaseExportInstance(
            name='export', domain="other-domain", xmlns='my_xmlns', case_type="case-type"
        )
        export.save()  # cleaned up in tearDown

        resp = self.client.get(
            reverse(EditNewCustomCaseExportView.urlname, args=[self.domain.name, export._id]),
        )
        self.assertEqual(resp.status_code, 404)

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


class ExportListCrossDomainTest(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.export = FormExportInstance(
            domain=self.domain.name, name='mine', auto_rebuild_enabled=True,
        )
        self.export.save()
        self.other_export = FormExportInstance(
            domain='other-domain', name='theirs', auto_rebuild_enabled=True,
        )
        self.other_export.save()

    def tearDown(self):
        delete_all_export_instances()
        super().tearDown()


    def test_get_saved_export_progress(self):
        def _get_saved_export_progress(export_id):
            return self.client.get(
                reverse('get_saved_export_progress', args=[self.domain.name]),
                {'export_instance_id': export_id, 'model_type': 'form', 'is_deid': 'false'},
            )
        assert _get_saved_export_progress(self.export._id).status_code == 200
        assert _get_saved_export_progress(self.other_export._id).status_code == 404


    def test_toggle_saved_export_enabled(self):
        def _toggle_saved_export_enabled(export_id):
            return self.client.post(
                reverse('toggle_saved_export_enabled', args=[self.domain.name]),
                {'export_id': export_id, 'is_deid': 'false', 'is_auto_rebuild_enabled': 'true'},
            )
        assert _toggle_saved_export_enabled(self.export._id).status_code == 200
        assert _toggle_saved_export_enabled(self.other_export._id).status_code == 404
        assert FormExportInstance.get(self.other_export._id).auto_rebuild_enabled


    @patch('corehq.apps.export.views.list.rebuild_saved_export')
    def test_update_emailed_export_data(self, rebuild_saved_export):
        def _update_emailed_export_data(export_id):
            return self.client.post(
                reverse('update_emailed_export_data', args=[self.domain.name]),
                {'export_id': export_id, 'is_deid': 'false'},
            )
        assert _update_emailed_export_data(self.export._id).status_code == 200
        assert rebuild_saved_export.call_count == 1

        assert _update_emailed_export_data(self.other_export._id).status_code == 404
        assert rebuild_saved_export.call_count == 1


    def test_commit_filters(self):
        def _commit_filters(export_id):
            return self.client.post(
                reverse('commit_filters', args=[self.domain.name]),
                {
                    'export_id': export_id,
                    'model_type': 'form',
                    'form_data': json.dumps(
                        {
                            'date_range': 'last7',
                            'emwf_form_filter': [],
                        }
                    ),
                },
            )
        response = _commit_filters(self.export._id)
        assert response.status_code == 200
        assert json.loads(response.content)['success'] is True

        assert _commit_filters(self.other_export._id).status_code == 404
        assert FormExportInstance.get(self.other_export._id)._rev == self.other_export._rev

    def test_download_daily_saved_export(self):
        response = self.client.get(reverse(
            'download_daily_saved_export',
            args=[self.domain.name, self.other_export._id],
        ))
        assert response.status_code == 404
        assert FormExportInstance.get(self.other_export._id).last_accessed is None


class ExportDownloadCrossDomainTest(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.other_export = FormExportInstance(domain='other-domain', name='theirs')
        self.other_export.save()

    def tearDown(self):
        delete_all_export_instances()
        super().tearDown()

    def _post(self, urlname):
        return self.client.post(
            reverse(urlname, args=[self.domain.name]),
            {
                'form_or_case': 'form',
                'sms_export': 'false',
                'exports': json.dumps([{'export_id': self.other_export._id}]),
                'form_data': json.dumps({
                    'date_range': '2020-01-01 to 2020-12-31', 'emw': '',
                }),
            },
        )

    @patch('corehq.apps.export.views.download.get_export_download')
    def test_prepare_custom_export_rejects_other_domain(self, get_export_download):
        assert self._post('prepare_custom_export').status_code == 404
        assert get_export_download.call_count == 0

    @patch('corehq.apps.export.views.download.build_form_multimedia_zipfile')
    def test_prepare_form_multimedia_rejects_other_domain(self, build_form_multimedia_zipfile):
        assert self._post('prepare_form_multimedia').status_code == 404
        assert build_form_multimedia_zipfile.delay.call_count == 0


class ExportSchemaAndMultimediaCrossDomainTest(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.export = FormExportInstance(domain=self.domain.name, name='mine')
        self.export.save()
        self.other_export = FormExportInstance(domain='other-domain', name='theirs')
        self.other_export.save()

    def tearDown(self):
        delete_all_export_instances()
        super().tearDown()


    def test_has_multimedia(self):
        def _has_multimedia(export_id):
            return self.client.get(
                reverse('has_multimedia', args=[self.domain.name]),
                {'export_id': export_id, 'form_or_case': 'form'},
            )
        assert _has_multimedia(self.export._id).status_code == 200
        assert _has_multimedia(self.other_export._id).status_code == 404

    @patch('corehq.apps.export.views.download._render_det_download')
    def test_download_det_schema(self, render_det):
        render_det.return_value = HttpResponse()

        my_det = self.client.get(reverse(
            'download-det-schema', args=[self.domain.name, self.export._id]))
        assert my_det.status_code == 200
        assert render_det.call_count == 1

        other = self.client.get(reverse(
            'download-det-schema', args=[self.domain.name, self.other_export._id]))
        assert other.status_code == 404
        assert render_det.call_count == 1  # still at 1


class ExportEditDeleteCopyCrossDomainTest(ViewTestCase):

    def setUp(self):
        super().setUp()
        self.export = FormExportInstance(domain=self.domain.name, name='mine')
        self.export.save()
        self.other_export = FormExportInstance(domain='other-domain', name='theirs')
        self.other_export.save()

    def tearDown(self):
        delete_all_export_instances()
        super().tearDown()

    def _delete(self, export_id, post=None):
        return self.client.post(
            reverse('delete_new_custom_export', args=[self.domain.name, 'form', export_id]),
            urlencode(post or {}),
            content_type='application/x-www-form-urlencoded'
        )

    def test_delete_url_export(self):
        assert self._delete(self.export._id).status_code == 302
        with pytest.raises(ResourceNotFound):
            FormExportInstance.get(self.export._id)
        assert self._delete(self.other_export._id).status_code == 404
        assert FormExportInstance.get(self.other_export._id) is not None

    def test_delete_list_export(self):
        response = self._delete(self.export._id, post={
            'count': '2',
            'deleteList': json.dumps([{'id': self.other_export._id}]),
        })
        assert response.status_code == 404
        assert FormExportInstance.get(self.export._id) is not None
        assert FormExportInstance.get(self.other_export._id) is not None

        tmp_export = FormExportInstance(domain=self.domain.name, name='my-tmp-export')
        tmp_export.save()
        response = self._delete(self.export._id, post={
            'count': '2',
            'deleteList': json.dumps([{'id': tmp_export._id}]),
        })
        assert response.status_code == 200
        with pytest.raises(ResourceNotFound):
            FormExportInstance.get(self.export._id)
        with pytest.raises(ResourceNotFound):
            FormExportInstance.get(tmp_export._id)

    def test_copy_export(self):
        def _copy(export_id):
            return self.client.get(
                reverse('copy_export', args=[self.domain.name, export_id]),
                follow=False,
            )
        before = len(get_form_exports_by_domain(self.domain.name))
        assert _copy(self.export._id).status_code == 302
        assert len(get_form_exports_by_domain(self.domain.name)) == before + 1

        assert _copy(self.other_export._id).status_code == 404


    def test_edit_export_name(self):
        def _edit_name(export_id, value):
            return self.client.post(
                reverse('edit_export_name', args=[self.domain.name, export_id]),
                urlencode({'value': value}),
                content_type='application/x-www-form-urlencoded',
            )
        assert _edit_name(self.export._id, 'renamed').status_code == 200
        assert FormExportInstance.get(self.export._id).name == 'renamed'

        assert _edit_name(self.other_export._id, 'hacked').status_code == 404
        assert FormExportInstance.get(self.other_export._id).name == 'theirs'
