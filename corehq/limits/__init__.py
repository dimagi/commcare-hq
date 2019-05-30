from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

from django.apps import AppConfig


class LimitsAppConfig(AppConfig):
    name = 'corehq.limits'


default_app_config = 'corehq.limits.LimitsAppConfig'
