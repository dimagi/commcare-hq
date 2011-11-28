from django.contrib import admin
from corehq.apps.sms.models import MessageLogOld

class MessageLogAdmin(admin.ModelAdmin):
    model = MessageLogOld
    list_display = ["text", "phone_number", "date", "direction", "domain"]
    list_filter = ["domain", "phone_number", "date", "direction"]

admin.site.register(MessageLogOld, MessageLogAdmin)
