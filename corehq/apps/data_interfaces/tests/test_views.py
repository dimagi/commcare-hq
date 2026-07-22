from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from django_prbac.models import Grant, Role

from corehq import privileges
from corehq.apps.data_dictionary.models import CaseProperty, CaseType
from corehq.apps.data_interfaces.interfaces import FormManagementMode
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    BulkAsyncJob,
    CaseRuleAction,
    UpdateCaseDefinition,
)
from corehq.apps.data_interfaces.views import (
    AutomaticUpdateRuleListView,
    DeduplicationRuleCreateView,
    XFormManagementView,
    _job_percent,
    _xform_management_job_context,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
from corehq.form_processor.models import XFormInstance


@override_settings(REQUIRE_TWO_FACTOR_FOR_SUPERUSERS=False)
class AutomaticUpdateRuleListViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain'
        cls.domain_obj = cls._create_domain(cls.domain)
        cls.user = cls._create_web_user()

        # Create a role, then link data_cleanup permission to it
        cls.test_role = Role.objects.create(name='test-role', slug='test-role', description='test-role')
        (data_cleanup_permission, _created) = Role.objects.get_or_create(
            slug=privileges.DATA_CLEANUP,
            name=privileges.Titles.get_name_from_privilege(privileges.DATA_CLEANUP)
        )
        Grant.objects.create(from_role=cls.test_role, to_role=data_cleanup_permission)

    def test_can_delete_existing_rule(self):
        rule = self._create_rule()
        deletion_request = self._create_deletion_request(rule.id)

        AutomaticUpdateRuleListView.as_view()(deletion_request, domain=self.domain)

        # the rule is only 'soft' deleted, so it remains in the database
        deleted_rule = AutomaticUpdateRule.objects.get(id=rule.id)
        self.assertTrue(deleted_rule.deleted)

    @classmethod
    def _create_web_user(cls):
        # A Couch user is required for logout
        existing_user = WebUser.get_by_username('test-user')
        if existing_user:
            existing_user.delete('', deleted_by=None)
        user = WebUser.create('', 'test-user', 'mockmock', None, None)
        user.is_superuser = True
        user.is_authenticated = True
        user.save()
        cls.addClassCleanup(user.delete, '', deleted_by=None)
        return user

    @classmethod
    def _create_domain(cls, name):
        domain_obj = create_domain(name)
        cls.addClassCleanup(domain_obj.delete)
        return domain_obj

    def _create_rule(self, domain='test-domain', name='Test Rule', close_case=True, upstream_id=None):
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name=name,
            active=True,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
            case_type='person',
            filter_on_server_modified=True,
            server_modified_boundary=None,
            upstream_id=upstream_id
        )

        if close_case:
            close_case_definition = UpdateCaseDefinition.objects.create(close_case=True)
            action = CaseRuleAction(rule=rule)
            action.definition = close_case_definition
            action.save()

        return rule

    def _create_deletion_request(self, id):
        request = RequestFactory().post('/somepath', {'action': 'delete', 'id': id})
        request.domain = self.domain
        request.user = self.user
        request.role = self.test_role
        return request


class XFormManagementPostTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'xform-mgmt-test'
        cls.blob_db = TemporaryFilesystemBlobDB()
        cls.addClassCleanup(cls.blob_db.close)

    def test_post_creates_job_and_enqueues(self):
        request = RequestFactory().post(
            '/x', {'mode': 'archive', 'xform_ids': ['form-1', 'form-2']})
        request.couch_user = WebUser(username='someone')
        request.can_access_all_locations = True

        view = XFormManagementView()
        view.request = request
        view.args = ()
        view.kwargs = {'domain': self.domain}

        with patch(
            'corehq.apps.data_interfaces.views.bulk_form_action_async.delay'
        ) as mock_delay:
            response = view.post(request)

        assert response.status_code == 302
        job = BulkAsyncJob.objects.get(domain=self.domain)
        assert job.model is XFormInstance
        assert job.action == BulkAsyncJob.Action.ARCHIVE
        assert job.requested_count == 2
        assert job.get_requested_ids() == ['form-1', 'form-2']
        mock_delay.assert_called_once_with(job.id.hex, self.domain)
        # the redirect (poll) url includes the job id
        assert job.id.hex in response['Location']

    def test_post_with_no_forms_is_rejected(self):
        request = RequestFactory().post('/x', {'mode': 'archive'})
        request.couch_user = WebUser(username='someone')
        request.can_access_all_locations = True

        view = XFormManagementView()
        view.request = request
        view.args = ()
        view.kwargs = {'domain': self.domain}

        response = view.post(request)

        assert response.status_code == 400
        assert not BulkAsyncJob.objects.filter(domain=self.domain).exists()


class XFormManagementJobPollTests(TestCase):

    TEMPLATE = 'data_interfaces/partials/xform_management_status.html'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'xform-poll-test'
        cls.domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(cls.domain_obj.delete)
        cls.blob_db = TemporaryFilesystemBlobDB()
        cls.addClassCleanup(cls.blob_db.close)

    def _job(self, **kw):
        defaults = dict(domain=self.domain, model=XFormInstance,
                        action=BulkAsyncJob.Action.ARCHIVE, requested_by='u')
        defaults.update(kw)
        return BulkAsyncJob(**defaults)

    def test_job_percent_zero_when_nothing_requested(self):
        assert _job_percent(self._job(requested_count=0)) == 0

    def test_job_percent_ratio(self):
        assert _job_percent(self._job(requested_count=4, processed_count=1)) == 25

    def test_context_running(self):
        job = self._job(status=BulkAsyncJob.Status.RUNNING,
                        requested_count=4, processed_count=1)
        ctx = _xform_management_job_context(job, FormManagementMode('archive'))
        assert ctx['is_done'] is False
        assert ctx['has_failed'] is False
        assert ctx['progress']['percent'] == 25
        assert ctx['download_id'] == job.id.hex

    def test_context_complete_reads_skipped(self):
        job = self._job(status=BulkAsyncJob.Status.COMPLETE, requested_count=2,
                        processed_count=2, succeeded_count=1)
        job.set_skipped({'not_found': ['a']})
        ctx = _xform_management_job_context(job, FormManagementMode('archive'))
        assert ctx['is_done'] is True
        assert ctx['has_failed'] is False
        assert ctx['succeeded_count'] == 1
        assert ctx['skipped'] == {'not_found': ['a']}

    def test_context_failed_has_no_skipped(self):
        job = self._job(status=BulkAsyncJob.Status.FAILED, requested_count=2)
        ctx = _xform_management_job_context(job, FormManagementMode('archive'))
        assert ctx['is_done'] is True
        assert ctx['has_failed'] is True
        assert ctx['skipped'] == {}

    def test_template_running_shows_percent_not_ready(self):
        job = self._job(status=BulkAsyncJob.Status.RUNNING,
                        requested_count=4, processed_count=1)
        ctx = _xform_management_job_context(job, FormManagementMode('archive'))
        html = render_to_string(self.TEMPLATE, ctx)
        assert 'ready_' not in html
        assert '25%' in html

    def test_template_complete_shows_ready_sentinel_and_counts(self):
        job = self._job(status=BulkAsyncJob.Status.COMPLETE, requested_count=2,
                        processed_count=2, succeeded_count=2)
        job.set_skipped({})
        ctx = _xform_management_job_context(job, FormManagementMode('archive'))
        html = render_to_string(self.TEMPLATE, ctx)
        assert f'ready_{job.id.hex}' in html
        assert '2 forms processed successfully' in html

    def test_template_legacy_id_shows_processing_message(self):
        html = render_to_string(self.TEMPLATE, {'legacy': True, 'download_id': 'dl-abc123'})
        assert 'ready_dl-abc123' in html   # sentinel so polling stops
        assert 'being processed' in html

    def test_job_lookup_is_scoped_to_domain(self):
        job = self._job()
        job.save()
        assert BulkAsyncJob.objects.filter(id=job.id, domain=self.domain).exists()
        assert not BulkAsyncJob.objects.filter(id=job.id, domain='another-domain').exists()

    def test_poll_requires_authentication(self):
        # A RUNNING job would render 200 if the view body were reached, so an
        # unauthenticated request being redirected proves the auth decorators
        # are applied to the poll view.
        job = self._job(status=BulkAsyncJob.Status.RUNNING,
                        requested_count=4, processed_count=1)
        job.save()
        url = reverse('xform_management_job_poll', args=[self.domain, job.id.hex])
        response = self.client.get(url, {'mode': 'archive'})
        assert response.status_code == 302
        assert '/login/' in response['Location']


class DeduplicationRuleCreateViewTests(TestCase):
    def test_system_properties_are_included_with_case_properties(self):
        case_type = CaseType.objects.create(name='case', domain=self.domain)
        CaseProperty.objects.create(name='prop1', case_type=case_type)
        CaseProperty.objects.create(name='prop2', case_type=case_type)

        prop_dict = DeduplicationRuleCreateView.get_augmented_data_dict_props_by_case_type(self.domain)

        self.assertEqual(set(prop_dict['case']), {'name', 'owner_id', 'prop1', 'prop2'})

    def test_system_properties_work_with_duplicate_case_properties(self):
        case_type = CaseType.objects.create(name='case', domain=self.domain)
        CaseProperty.objects.create(name='name', case_type=case_type)
        CaseProperty.objects.create(name='owner_id', case_type=case_type)

        prop_dict = DeduplicationRuleCreateView.get_augmented_data_dict_props_by_case_type(self.domain)

        self.assertEqual(set(prop_dict['case']), {'name', 'owner_id'})

    def test_system_properties_override_deprecated_properties(self):
        case_type = CaseType.objects.create(name='case', domain=self.domain)
        CaseProperty.objects.create(name='prop1', case_type=case_type)
        CaseProperty.objects.create(name='name', deprecated=True, case_type=case_type)

        prop_dict = DeduplicationRuleCreateView.get_augmented_data_dict_props_by_case_type(self.domain)

        self.assertEqual(set(prop_dict['case']), {'name', 'owner_id', 'prop1'})

    def test_properties_are_sorted(self):
        case_type = CaseType.objects.create(name='cookies', domain=self.domain)
        CaseProperty.objects.create(name='golden_oreos', case_type=case_type)
        CaseProperty.objects.create(name='peanut_butter_oreos', case_type=case_type)
        CaseProperty.objects.create(name='oreos', case_type=case_type)

        prop_dict = DeduplicationRuleCreateView.get_augmented_data_dict_props_by_case_type(self.domain)
        self.assertEqual(
            prop_dict['cookies'],
            ['golden_oreos', 'name', 'oreos', 'owner_id', 'peanut_butter_oreos']
        )

    def setUp(self):
        self.domain = 'test-domain'
