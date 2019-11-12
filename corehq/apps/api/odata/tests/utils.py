import base64

from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from corehq.apps.domain.utils import clear_domain_names
from tastypie.models import ApiKey

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionAdjustment,
)
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted, reset_es_index


class OdataTestMixin(object):

    view_urlname = None

    @classmethod
    def _set_up_class(cls):
        cls.client = Client()
        clear_domain_names('test_domain')
        cls.domain = Domain(name='test_domain')
        cls.domain.save()
        cls.web_user = WebUser.create(cls.domain.name, 'test_user', 'my_password')
        cls._setup_user_permissions()

    @classmethod
    def _teardownclass(cls):
        cls.domain.delete()

    @classmethod
    def _setup_accounting(cls):
        call_command('cchq_prbac_bootstrap')
        cls.account, _ = BillingAccount.get_or_create_account_by_domain(cls.domain.name, created_by='')
        plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.ADVANCED)
        cls.subscription = Subscription.new_domain_subscription(cls.account, cls.domain.name, plan_version)

    @classmethod
    def _teardown_accounting(cls):
        SubscriptionAdjustment.objects.all().delete()
        cls.subscription.delete()
        cls.account.delete()

    @classmethod
    def _setup_user_permissions(cls):
        cls.web_user.set_role(cls.domain.name, 'admin')
        cls.web_user.save()

    def _execute_query(self, credentials):
        return self.client.get(self.view_url, HTTP_AUTHORIZATION='Basic ' + credentials)

    @classmethod
    def _get_correct_credentials(cls):
        return OdataTestMixin._get_basic_credentials(cls.web_user.username, 'my_password')

    @staticmethod
    def _get_basic_credentials(username, password):
        return base64.b64encode("{}:{}".format(username, password).encode('utf-8')).decode('utf-8')


class CaseOdataTestMixin(OdataTestMixin):

    @property
    def view_url(self):
        return reverse(self.view_urlname, kwargs={'domain': self.domain.name, 'config_id': 'my_config_id'})


class FormOdataTestMixin(OdataTestMixin):

    @property
    def view_url(self):
        return reverse(self.view_urlname, kwargs={'domain': self.domain.name, 'config_id': 'my_config_id'})


def generate_api_key_from_web_user(web_user):
    api_key = ApiKey.objects.get_or_create(user=web_user.get_django_user())[0]
    api_key.key = api_key.generate_key()
    api_key.save()
    return api_key


def setup_es_case_index():
    reset_es_index(CASE_INDEX_INFO)


def setup_es_form_index():
    reset_es_index(XFORM_INDEX_INFO)


def ensure_es_case_index_deleted():
    ensure_index_deleted(CASE_INDEX_INFO.index)


def ensure_es_form_index_deleted():
    ensure_index_deleted(XFORM_INDEX_INFO.index)
