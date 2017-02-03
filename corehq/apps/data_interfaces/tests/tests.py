from os.path import abspath, dirname, join

from django.test import TestCase
from django.test import Client

from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from corehq.form_processor.utils.xform import TestFormMetadata, get_simple_wrapped_form
from corehq.util.context_managers import drop_connected_signals
from corehq.util.workbook_json.excel import WorkbookJSONReader
from couchforms.signals import xform_archived

from django_prbac.models import UserRole, Role, Grant
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.apps.data_interfaces.utils import archive_forms_old
from corehq import privileges, toggles

THISDIR = dirname(abspath(__file__))
BASE_PATH = join(THISDIR, 'files')
BASIC_XLSX = 'basic_forms_bulk.xlsx'
DOMAIN_NAME = 'test'
MISSING_XLSX = 'missing_forms_bulk.xlsx'
MALFORM_XLSX = 'malformatted_forms_bulk.xlsx'
WRONG_FILETYPE = 'wrong_file.xyz'


class BulkArchiveForms(TestCase):

    @classmethod
    def setUpClass(cls):
        create_domain(DOMAIN_NAME)
        cls.password = "password"
        username = "ben"
        email = "ben@domain.com"
        cls.user = WebUser.create(DOMAIN_NAME, username, cls.password, email, is_admin=True)

        django_user = cls.user.get_django_user()
        try:
            cls.user_role = UserRole.objects.get(user=django_user)
        except UserRole.DoesNotExist:
            user_privs = Role.objects.get_or_create(
                name="Privileges for %s" % django_user.username,
                slug="%s_privileges" % django_user.username,
            )[0]
            cls.user_role = UserRole.objects.create(
                user=django_user,
                role=user_privs,
            )

        cls.bulk_role = Role.objects.filter(slug=privileges.BULK_CASE_MANAGEMENT)[0]

        toggles.BULK_ARCHIVE_FORMS.set(username, True)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        Domain.get_by_name(DOMAIN_NAME, strict=True).delete()
        toggles.BULK_ARCHIVE_FORMS.set(cls.user.username, False)

    def setUp(self):
        self.client = Client()
        self.url = '/a/{}/data/edit/archive_forms/'.format(DOMAIN_NAME)

        Grant.objects.get_or_create(from_role=self.user_role.role, to_role=self.bulk_role)
        Role.get_cache().clear()

        self.client.login(username=self.user.username, password=self.password)

    def test_bulk_archive_get_form(self):

        # Logged in
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['bulk_upload']['download_url'],
                         '/static/data_interfaces/xlsx/forms_bulk_example.xlsx')

        grant = Grant.objects.get(
            from_role=self.user_role.role,
            to_role=self.bulk_role
        )
        grant.delete()
        Role.get_cache().clear()

        # Revoked privileges should not render form
        response = self.client.get(self.url)
        self.assertFalse('bulk_upload' in response.context)

    def test_bulk_archive_missing_file(self):
        response = self.client.post(self.url, follow=True)

        # Huge hack for determining what has been sent in django messages object.
        # Need to find out how to inspect messages after redirect
        self.assertIn('No files uploaded', response.content)

    def test_bulk_archive_wrong_filetype(self):
        with open(join(BASE_PATH, WRONG_FILETYPE)) as fp:
            response = self.client.post(self.url, {'bulk_upload_file': fp}, follow=True)
            self.assertIn('CommCare HQ does not support that file type.', response.content)

    def test_bulk_archive_basic(self):
        with open(join(BASE_PATH, BASIC_XLSX)) as fp:
            response = self.client.post(self.url, {'bulk_upload_file': fp}, follow=True)
            self.assertIn('We received your file and are processing it.', response.content)


class BulkArchiveFormsUnit(TestCase):

    XFORMS = {
        'PRESENT': 'present_id',
        'PRESENT_2': 'present_2_id'
    }

    def setUp(self):
        self.username = "ben"
        self.xforms = {}

        for key, _id, in self.XFORMS.iteritems():
            meta = TestFormMetadata(domain=DOMAIN_NAME)
            self.xforms[_id] = get_simple_wrapped_form(_id, metadata=meta)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms(DOMAIN_NAME)

    @run_with_all_backends
    def test_archive_forms_basic(self):
        uploaded_file = WorkbookJSONReader(join(BASE_PATH, BASIC_XLSX))

        with drop_connected_signals(xform_archived):
            response = archive_forms_old(DOMAIN_NAME, 'user1', self.username, list(uploaded_file.get_worksheet()))
            print response

        # Need to re-get instance from DB to get updated attributes
        for key, _id in self.XFORMS.iteritems():
            self.assertTrue(FormAccessors(DOMAIN_NAME).get_form(_id).is_archived)

        self.assertEqual(len(response['success']), len(self.xforms))

    @run_with_all_backends
    def test_archive_forms_missing(self):
        uploaded_file = WorkbookJSONReader(join(BASE_PATH, MISSING_XLSX))

        with drop_connected_signals(xform_archived):
            response = archive_forms_old(DOMAIN_NAME, 'user1', self.username, list(uploaded_file.get_worksheet()))

        for key, _id in self.XFORMS.iteritems():
            self.assertTrue(FormAccessors(DOMAIN_NAME).get_form(_id).is_archived)

        self.assertEqual(len(response['success']), len(self.xforms))
        self.assertEqual(len(response['errors']), 1,
                         "One error for trying to archive a missing form")

    @run_with_all_backends
    def test_archive_forms_wrong_domain(self):
        uploaded_file = WorkbookJSONReader(join(BASE_PATH, BASIC_XLSX))

        response = archive_forms_old('wrong_domain', 'user1', self.username, list(uploaded_file.get_worksheet()))

        self.assertEqual(len(response['errors']), len(self.xforms), "Error when wrong domain")
