from django.contrib import admin

from .models import DomainUserHistory


@admin.register(DomainUserHistory)
class DomainUserHistoryAdmin(admin.ModelAdmin):
    model = DomainUserHistory
    list_display = ('domain', 'record_date', 'num_users')
    list_filter = ('domain', 'record_date')
