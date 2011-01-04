from django.contrib import admin
from corehq.apps.sms.models import MessageLog

admin.site.register(MessageLog)
