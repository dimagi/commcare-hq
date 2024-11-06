import json
from django.test import TestCase, RequestFactory
from django_prbac.models import Role, Grant, UserRole
from corehq import privileges
import base64
from datetime import datetime, timezone
from corehq.apps.users.models import WebUser, CommCareUser, HQApiKey
from corehq.apps.accounting.tests import generator
from corehq.apps.domain.models import Domain
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.forms import form_adapter
from corehq.apps.enterprise.api.resources import FormSubmissionResource
from corehq.form_processor.tests.utils import create_form_for_test


@es_test(requires=[form_adapter])
class FormSubmissionResourceTests(TestCase):
    def test_happy_path(self):

        self._create_enterprise_account_covering_domains(['test-domain-1', 'test-domain-2'])

        enterprise_admin = self._create_enterprise_admin('test-admin@dimagi.com', 'test-domain-1')
        django_user = enterprise_admin.get_django_user()
        api_key = HQApiKey.objects.create(user=django_user, key='1234', name='TestKey')

        mobile_user_1 = self._create_mobile_user('mobile1@test.com', 'test-domain-1')
        mobile_user_2 = self._create_mobile_user('mobile2@test.com', 'test-domain-2')

        form1 = self._create_form(mobile_user_1, form_id='1234', received_on=datetime(year=2004, month=10, day=11))
        form2 = self._create_form(mobile_user_2, form_id='2345', received_on=datetime(year=2004, month=10, day=12))
        form_adapter.bulk_index([form1, form2], refresh=True)

        request = self._create_api_request(enterprise_admin, 'test-domain-1', api_key)

        resource = FormSubmissionResource()
        response = resource.dispatch_list(request)
        result = json.loads(response.content)
        resulting_forms = result['value']
        self.assertEqual([form['form_id'] for form in resulting_forms], ['1234', '2345'])

    def _create_form(self, user, form_id=None, received_on=None):
        form_data = {
            '#type': 'fake-type',
            '@name': 'TestForm',
            'meta': {
                'userID': user._id,
                'username': user.name,
                'instanceID': form_id,
            },
        }
        return create_form_for_test(
            user.domain,
            user_id=user._id,
            form_data=form_data,
            form_id=form_id,
            received_on=received_on,
        )

    def _create_enterprise_account_covering_domains(self, domains):
        billing_account = generator.billing_account('test-admin@dimagi.com', 'test-admin@dimagi.com')
        billing_account.enterprise_admin_emails = ['test-admin@dimagi.com']
        billing_account.save()

        for domain in domains:
            domain_obj = Domain(name=domain, is_active=True)
            domain_obj.save()
            self.addCleanup(domain_obj.delete)

            generator.generate_domain_subscription(
                billing_account, domain_obj, datetime.now(timezone.utc), None, is_active=True
            )

        return billing_account

    def _create_enterprise_admin(self, email, domain):
        user = WebUser.create(
            domain, email, 'test123', None, None, email)
        user.is_superuser = True
        user.save()

        self.addCleanup(user.delete, None, deleted_by=None)

        role = Role.objects.create(slug="test_role")
        UserRole.objects.create(user=user.get_django_user(), role=role)
        accounting_admin_role = Role.objects.get_or_create(
            name="Accounting Admin",
            slug=privileges.ACCOUNTING_ADMIN,
        )[0]
        Grant.objects.create(from_role=role, to_role=accounting_admin_role)

        return user

    def _create_mobile_user(self, username, domain):
        user = CommCareUser.create(domain, username, 'test123', None, None)
        self.addCleanup(user.delete, None, deleted_by=None)
        return user

    def _create_api_request(self, user, domain, api_key):
        auth_string = f'{user.username}:{api_key.key}'
        factory = RequestFactory()
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        request = factory.get(
            '/',
            {'startdate': '2004-10-10', 'enddate': '2004-11-10'},
            HTTP_AUTHORIZATION=f'basic {encoded_auth}'
        )
        request.couch_user = user
        request.user = user.get_django_user()
        request.domain = domain

        return request
