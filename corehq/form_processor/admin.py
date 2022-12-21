from django.contrib import admin
from corehq.form_processor.models import XFormInstance, CommCareCase, LedgerValue


@admin.register(XFormInstance)
class XFormInstanceAdmin(admin.ModelAdmin):
    date_hierarchy = 'received_on'
    list_display = ('form_id', 'domain', 'xmlns', 'user_id', 'received_on')
    list_filter = ('domain',)
    ordering = ('received_on',)


@admin.register(CommCareCase)
class CommCareCaseAdmin(admin.ModelAdmin):
    date_hierarchy = 'server_modified_on'
    list_display = ('case_id', 'domain', 'type', 'name', 'server_modified_on')
    list_filter = ('domain', 'closed', 'type')
    ordering = ('server_modified_on',)


@admin.register(LedgerValue)
class LedgerValueAdmin(admin.ModelAdmin):
    date_hierarchy = 'last_modified'
    list_display = ('domain', 'section_id', 'case', 'entry_id', 'balance', 'last_modified')
    list_filter = ('domain', 'section_id', 'last_modified')
    ordering = ('last_modified',)
