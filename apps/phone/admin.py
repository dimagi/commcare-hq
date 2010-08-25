from django.contrib import admin
from corehq.apps.phone.models import *

admin.site.register(PhoneUserInfo)
admin.site.register(PhoneBackup)

