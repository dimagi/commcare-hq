from __future__ import absolute_import
from __future__ import unicode_literals

import base64

from django.test import Client
from django.urls import reverse

from elasticsearch.exceptions import ConnectionError
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
from corehq.elastic import get_es_new
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup
from pillowtop.es_utils import initialize_index_and_mapping


class OdataTestMixin(object):

    view_urlname = None

    @classmethod
    def _set_up_class(cls):
        cls.client = Client()
        cls.domain = Domain(name='test_domain')
        cls.domain.save()
        cls.web_user = WebUser.create(cls.domain.name, 'test_user', 'my_password')
        cls._setup_user_permissions()

    @classmethod
    def _teardownclass(cls):
        cls.domain.delete()
        cls.web_user.delete()

    @classmethod
    def _setup_accounting(cls):
        cls.account, _ = BillingAccount.get_or_create_account_by_domain(cls.domain.name, created_by='')
        plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.STANDARD)
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


class DeprecatedCaseOdataTestMixin(OdataTestMixin):

    @property
    def view_url(self):
        return reverse(self.view_urlname, kwargs={'domain': self.domain.name})


class DeprecatedFormOdataTestMixin(OdataTestMixin):

    @property
    def view_url(self):
        return reverse(self.view_urlname, kwargs={'domain': self.domain.name, 'app_id': 'my_app_id'})


class CaseOdataTestMixin(OdataTestMixin):

    @property
    def view_url(self):
        return reverse(self.view_urlname, kwargs={'domain': self.domain.name})


class FormOdataTestMixin(OdataTestMixin):

    @property
    def view_url(self):
        return reverse(self.view_urlname, kwargs={'domain': self.domain.name})



def generate_api_key_from_web_user(web_user):
    api_key = ApiKey.objects.get_or_create(user=web_user.get_django_user())[0]
    api_key.key = api_key.generate_key()
    api_key.save()
    return api_key


def setup_es_case_index():
    _setup_es_index(CASE_INDEX_INFO)


def setup_es_form_index():
    _setup_es_index(XFORM_INDEX_INFO)


def _setup_es_index(index_info):
    with trap_extra_setup(ConnectionError):
        elasticsearch_instance = get_es_new()
        initialize_index_and_mapping(elasticsearch_instance, index_info)


def ensure_es_case_index_deleted():
    _ensure_es_index_deleted(CASE_INDEX_INFO)


def ensure_es_form_index_deleted():
    _ensure_es_index_deleted(XFORM_INDEX_INFO)


def _ensure_es_index_deleted(index_info):
    ensure_index_deleted(index_info.index)
