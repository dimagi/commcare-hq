from __future__ import absolute_import
from __future__ import unicode_literals

import base64

from django.test import Client
from django.urls import reverse

from tastypie.models import ApiKey

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser


class OdataTestMixin(object):

    view_urlname = None

    @classmethod
    def _setupclass(cls):
        cls.client = Client()
        cls.domain = Domain(name='test_domain')
        cls.domain.save()
        cls.web_user = WebUser.create(cls.domain.name, 'test_user', 'my_password')

    @classmethod
    def _teardownclass(cls):
        cls.domain.delete()
        cls.web_user.delete()

    def _execute_query(self, credentials):
        return self.client.get(self.view_url, HTTP_AUTHORIZATION='Basic ' + credentials)

    @staticmethod
    def _get_correct_credentials():
        return CaseOdataTestMixin._get_basic_credentials('test_user', 'my_password')

    @staticmethod
    def _get_basic_credentials(username, password):
        return base64.b64encode("{}:{}".format(username, password).encode('utf-8')).decode('utf-8')


class CaseOdataTestMixin(OdataTestMixin):

    @property
    def view_url(self):
        return reverse(self.view_urlname, kwargs={'domain': self.domain.name})


class FormOdataTestMixin(OdataTestMixin):

    @property
    def view_url(self):
        return reverse(self.view_urlname, kwargs={'domain': self.domain.name, 'app_id': 'my_app_id'})


def generate_api_key_from_web_user(web_user):
    api_key = ApiKey.objects.get_or_create(user=web_user.get_django_user())[0]
    api_key.key = api_key.generate_key()
    api_key.save()
    return api_key
