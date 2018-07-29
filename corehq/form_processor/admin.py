from __future__ import absolute_import
from __future__ import unicode_literals
from django.contrib import admin
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL, LedgerValue


@admin.register(XFormInstanceSQL)
class XFormInstanceSQLAdmin(admin.ModelAdmin):
    date_hierarchy = 'received_on'
    list_display = ('form_id', 'domain', 'xmlns', 'user_id', 'received_on')
    list_filter = ('domain',)
    ordering = ('received_on',)


@admin.register(CommCareCaseSQL)
class CommCareCaseSQLAdmin(admin.ModelAdmin):
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
