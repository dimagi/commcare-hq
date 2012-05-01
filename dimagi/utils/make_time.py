from __future__ import absolute_import
from datetime import datetime
from pytz import timezone
from django.conf import settings

def make_time():
    return datetime.now(tz=timezone(settings.TIME_ZONE))