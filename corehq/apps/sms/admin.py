from django.contrib import admin
from corehq.apps.sms.models import MessageLog

class MessageLogAdmin(admin.ModelAdmin):
    model = MessageLog
    list_display = ["domain", "phone_number", "date", "direction", "text"]
    list_filter = ["domain", "phone_number", "date", "direction"]

admin.site.register(MessageLog, MessageLogAdmin)
