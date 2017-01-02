# encoding: utf-8
import json

from django.test import TestCase
from django.core.urlresolvers import reverse

from corehq.apps.users.models import WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.export.dbaccessors import (
    delete_all_export_instances,
    get_form_export_instances,
    get_case_export_instances,
)
from corehq.apps.export.views import (
    CreateNewCustomFormExportView,
    CreateNewCustomCaseExportView,
    EditNewCustomCaseExportView,
    EditNewCustomFormExportView,
)


class ExportViewTest(TestCase):

    @classmethod
    def setUpClass(cls):
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

    def setUp(self):
        self.client.login(username=self.username, password=self.password)

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
        exports = get_form_export_instances(self.domain.name)
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

        exports = get_case_export_instances(self.domain.name)
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
