from __future__ import absolute_import
from __future__ import unicode_literals
from django.apps import AppConfig


class EnikshayAppConfig(AppConfig):
    name = 'custom.enikshay'


default_app_config = 'custom.enikshay.EnikshayAppConfig'
