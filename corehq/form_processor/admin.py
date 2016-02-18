from django.contrib import admin
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL


# note: these require ALLOW_FORM_PROCESSING_QUERIES = True in your localsettings.py to work
@admin.register(XFormInstanceSQL)
class XFormInstanceSQLAdmin(admin.ModelAdmin):
    date_hierarchy = 'received_on'
    list_display = ('form_id', 'domain', 'xmlns', 'user_id', 'received_on')
    list_filter = ('domain',)
    ordering = ('received_on',)

admin.site.register(CommCareCaseSQL)
