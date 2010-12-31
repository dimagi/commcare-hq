from django.contrib import admin
from corehq.apps.auditor.models import * 
from django.contrib.auth.models import User


class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('id','user','event_class','description', 'event_date', 'summary')
    list_filter = ['user','event_class','description']
    
admin.site.register(AuditEvent, AuditEventAdmin)  
