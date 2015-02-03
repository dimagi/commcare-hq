from datetime import datetime

from django.test import TestCase
from django.test import Client

from couchforms.models import XFormInstance
from corehq.apps.users.models import CouchUser, WebUser, CommCareUser
from corehq.apps.data_interfaces.utils import archive_forms
from dimagi.utils.excel import WorkbookJSONReader

BASE_PATH = 'corehq/apps/data_interfaces/tests/files/'
BASIC_XLSX = 'basic_forms_bulk.xlsx'
MISSING_XLSX = 'missing_forms_bulk.xlsx'
MALFORM_XLSX = 'malformatted_forms_bulk.xlsx'
WRONG_FILETYPE = 'wrong_file.xyz'

class BulkArchiveForms(TestCase):

    def setUp(self):
        self.domain_name = 'test'
        self.password = "password"

        username = "ben"
        email = "ben@domain.com"

        self.client = Client()
        self.user = WebUser.create(self.domain_name, username, self.password, email)
        self.user.is_superuser = True
        self.user.save()
        self.url = '/a/{}/data/edit/archive_forms/'.format(self.domain_name)

        self.client.login(username=self.user.username, password=self.password)

    def tearDown(self):
        self.user.delete()

    def test_bulk_archive_get_form(self):

        # Logged in and super user
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['bulk_upload']['download_url'],
                         '/static/data_interfaces/files/forms_bulk_example.xlsx')

        # Logged out user
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302, "Should redirect to login")

        # Logged in but not a super user
        normal_user = WebUser.create(self.domain_name, 'muggle', self.password, 'b@b.com')
        self.client.login(username='muggle', password=self.password)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403, "User needs to be a superuser to access")
        self.client.logout()


    def test_bulk_archive_missing_file(self):
        response = self.client.post(self.url, follow=True)

        # Huge hack for determining what has been sent in django messages object.
        # Need to find out how to inspect messages after redirect
        self.assertIn('No files uploaded', response.content)

    def test_bulk_archive_wrong_filetype(self):
        with open(BASE_PATH + WRONG_FILETYPE) as fp:
            response = self.client.post(self.url, {'bulk_upload_file': fp}, follow=True)
            self.assertIn('CommCare HQ does not support that file type.', response.content)

    def test_bulk_archive_basic(self):
        with open(BASE_PATH + BASIC_XLSX) as fp:
            response = self.client.post(self.url, {'bulk_upload_file': fp}, follow=True)
            self.assertIn('We received your file and are processing it...', response.content)


class BulkArchiveFormsUnit(TestCase):

    XFORMS = {
        'PRESENT': 'present_id',
        'PRESENT_2': 'present_2_id'
    }


    def setUp(self):
        self.domain_name = 'test'
        self.password = "password"
        username = "ben"
        email = "ben@domain.com"
        self.user = WebUser.create(self.domain_name, username, self.password, email)
        self.xforms = {}

        for key, _id, in self.XFORMS.iteritems():
            self.xforms[_id] = XFormInstance(xmlns = 'fake-xmlns',
                                        domain = self.domain_name,
                                        received_on = datetime.utcnow(),
                                        form = {
                                            '#type': 'fake-type',
                                            '@xmlns': 'fake-xmlns'
                                        })
            self.xforms[_id]['_id'] = _id
            self.xforms[_id].save()

    def tearDown(self):
        self.user.delete()
        for key, xform, in self.xforms.iteritems():
            xform.delete()

    def test_archive_forms_basic(self):
        uploaded_file = WorkbookJSONReader("{}{}".format(BASE_PATH, BASIC_XLSX))

        response = archive_forms(self.user, list(uploaded_file.get_worksheet()))

        # Need to re-get instance from DB to get updated attributes
        for key, _id in self.XFORMS.iteritems():
            self.assertEqual(XFormInstance.get(_id).doc_type, 'XFormArchived')

        self.assertEqual(len(response['success']), len(self.xforms))

    def test_archive_forms_missing(self):
        uploaded_file = WorkbookJSONReader("{}{}".format(BASE_PATH, MISSING_XLSX))

        response = archive_forms(self.user, list(uploaded_file.get_worksheet()))

        for key, _id in self.XFORMS.iteritems():
            self.assertEqual(XFormInstance.get(_id).doc_type, 'XFormArchived')

        self.assertEqual(len(response['success']), len(self.xforms))
        self.assertEqual(len(response['errors']), 1, 
                         "One error for trying to archive a missing form")
