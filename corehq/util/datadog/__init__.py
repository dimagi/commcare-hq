from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf import settings
from datadog.dogstatsd.base import DogStatsd
import logging

datadog_logger = logging.getLogger('datadog')

COMMON_TAGS = ['environment:{}'.format(settings.SERVER_ENVIRONMENT)]

statsd = DogStatsd(constant_tags=COMMON_TAGS)
