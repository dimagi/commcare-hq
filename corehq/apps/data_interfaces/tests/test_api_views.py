import uuid
from contextlib import contextmanager
from unittest.mock import patch

from django.test import TestCase
from django.urls import resolve, reverse

from corehq import privileges
from corehq.apps.data_interfaces.models import BulkAsyncJob
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import (
    HQApiKey,
    HqPermissions,
    UserRole,
    WebUser,
)
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.util.test_utils import (
    flag_disabled,
    flag_enabled,
    privilege_enabled,
)

DOMAIN = 'bulk-action-view-test'
OTHER_DOMAIN = 'bulk-action-other-domain'
USERNAME = 'api-user@example.com'
PASSWORD = '************'

FULL_PERMISSIONS = {'edit_data': True, 'access_api': True}


def test_create_url_is_not_shadowed_by_the_form_resource():
    match = resolve(f'/a/{DOMAIN}/api/form/v1/bulk-action/')
    assert match.url_name == 'bulk_form_action'


def test_status_url_is_not_shadowed_by_the_form_resource():
    match = resolve(f'/a/{DOMAIN}/api/form/v1/bulk-action/{uuid.uuid4().hex}/')
    assert match.url_name == 'bulk_form_action_status'


@privilege_enabled(privileges.API_ACCESS, privileges.DATA_CLEANUP)
@flag_enabled('API_THROTTLE_WHITELIST')
@flag_enabled('BULK_FORM_ACTIONS_API')
class TestBulkFormActionApi(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.blob_db = TemporaryFilesystemBlobDB()
        cls.addClassCleanup(cls.blob_db.close)
        cls.domain = create_domain(DOMAIN)
        cls.addClassCleanup(cls.domain.delete)
        cls.other_domain = create_domain(OTHER_DOMAIN)
        cls.addClassCleanup(cls.other_domain.delete)

    @contextmanager
    def logged_in(self, permissions=None):
        role = UserRole.create(
            DOMAIN,
            'bulk-action-role',
            permissions=HqPermissions(**(permissions or FULL_PERMISSIONS)),
        )
        user = WebUser.create(
            DOMAIN, USERNAME, PASSWORD,
            created_by=None, created_via=None, role_id=role.get_id,
        )
        api_key = HQApiKey.objects.create(
            user=user.get_django_user(), name='bulk-action-test-key')
        self.client.defaults['HTTP_AUTHORIZATION'] = (
            f'ApiKey {USERNAME}:{api_key.plaintext_key}')
        try:
            yield user
        finally:
            del self.client.defaults['HTTP_AUTHORIZATION']
            user.delete(DOMAIN, deleted_by=None)
            role.delete()

    def create_url(self):
        return reverse('bulk_form_action', args=[DOMAIN])

    def status_url(self, job_id):
        return reverse('bulk_form_action_status', args=[DOMAIN, job_id])

    def post(self, payload):
        return self.client.post(
            self.create_url(), payload, content_type='application/json')

    def _job(self, domain=DOMAIN, model=XFormInstance):
        job = BulkAsyncJob(
            domain=domain,
            model=model,
            action=BulkAsyncJob.Action.ARCHIVE,
            requested_by=USERNAME,
        )
        job.set_requested_ids(['a', 'b'])
        job.save()
        return job

    def test_creates_job_and_enqueues_task(self):
        with self.logged_in(), patch(
            'corehq.apps.data_interfaces.api.views.bulk_form_action_async'
        ) as task:
            response = self.post({'action': 'archive', 'form_ids': ['a', 'b']})

        assert response.status_code == 202
        data = response.json()
        job = BulkAsyncJob.objects.get(id=data['id'])
        assert job.domain == DOMAIN
        assert job.model is XFormInstance
        assert job.action == 'archive'
        assert job.requested_by == USERNAME
        assert job.get_requested_ids() == ['a', 'b']
        task.delay.assert_called_once_with(job.id.hex, DOMAIN)

        assert data['status'] == 'pending'
        assert data['requested'] == 2
        assert data['skipped'] == {}
        assert data['status_url'].endswith(self.status_url(data['id']))

    def test_invalid_json_is_a_400(self):
        with self.logged_in():
            response = self.client.post(
                self.create_url(), 'not json', content_type='application/json')
        assert response.status_code == 400
        assert 'error' in response.json()

    def test_disallowed_methods_are_405(self):
        job = self._job()
        with self.logged_in():
            # GET on create endpoint
            assert self.client.get(self.create_url()).status_code == 405
            # POST on status endpoint
            assert self.client.post(
                self.status_url(job.id.hex), {},
                content_type='application/json').status_code == 405

    def test_requires_edit_data(self):
        job = self._job()
        with self.logged_in({'edit_data': False, 'access_api': True}):
            assert self.post({'action': 'archive', 'form_ids': ['a']}).status_code == 403
            assert self.client.get(self.status_url(job.id.hex)).status_code == 403

    def test_requires_access_api(self):
        job = self._job()
        with self.logged_in({'edit_data': True, 'access_api': False}):
            assert self.post({'action': 'archive', 'form_ids': ['a']}).status_code == 403
            assert self.client.get(self.status_url(job.id.hex)).status_code == 403

    def test_rejects_location_restricted_user(self):
        # LocationAccessMiddleware cannot enforce this since it runs before the API
        # key is authenticated, so require_access_all_locations does it instead
        job = self._job()
        with self.logged_in(FULL_PERMISSIONS | {'access_all_locations': False}):
            assert self.post({'action': 'archive', 'form_ids': ['a']}).status_code == 403
            assert self.client.get(self.status_url(job.id.hex)).status_code == 403
        assert BulkAsyncJob.objects.count() == 1  # no job was created

    @flag_disabled('BULK_FORM_ACTIONS_API')
    def test_requires_feature_flag(self):
        job = self._job()
        with self.logged_in():
            assert self.post({'action': 'archive', 'form_ids': ['a']}).status_code == 404
            assert self.client.get(self.status_url(job.id.hex)).status_code == 404
        assert BulkAsyncJob.objects.count() == 1  # no job was created

    def test_requires_authentication(self):
        job = self._job()
        assert self.post({'action': 'archive', 'form_ids': ['a']}).status_code == 401
        assert self.client.get(self.status_url(job.id.hex)).status_code == 401
        assert BulkAsyncJob.objects.count() == 1  # no job was created

    def test_returns_job_status(self):
        job = self._job()
        with self.logged_in():
            response = self.client.get(self.status_url(job.id.hex))

        assert response.status_code == 200
        data = response.json()
        assert data['id'] == job.id.hex
        assert data['action'] == 'archive'
        assert data['status'] == 'pending'
        assert data['requested'] == 2
        assert 'status_url' not in data

    def test_unknown_job_is_a_404(self):
        with self.logged_in():
            response = self.client.get(self.status_url(uuid.uuid4().hex))
        assert response.status_code == 404

    def test_malformed_job_id_is_a_404(self):
        with self.logged_in():
            response = self.client.get(self.status_url('not-a-uuid'))
        assert response.status_code == 404

    def test_job_in_another_domain_is_a_404(self):
        job = self._job(domain=OTHER_DOMAIN)
        with self.logged_in():
            response = self.client.get(self.status_url(job.id.hex))
        assert response.status_code == 404

    def test_non_form_job_is_a_404(self):
        job = self._job(model=CommCareCase)
        with self.logged_in():
            response = self.client.get(self.status_url(job.id.hex))
        assert response.status_code == 404
