from django.contrib import admin
from corehq.apps.sms.models import MessageLog

class MessageLogAdmin(admin.ModelAdmin):
    model = MessageLog
    list_display = ["text", "phone_number", "date", "direction", "domain"]
    list_filter = ["domain", "phone_number", "date", "direction"]

admin.site.register(MessageLog, MessageLogAdmin)
