from django.contrib import admin
from corehq.apps.data_interfaces.models import DomainCaseRuleRun


class DomainCaseRuleRunAdmin(admin.ModelAdmin):

    list_display = [
        'domain',
        'started_on',
        'finished_on',
        'status',
        'cases_checked',
        'num_updates',
        'num_closes',
        'num_related_updates',
        'num_related_closes',
    ]

    search_fields = [
        'domain',
    ]

    ordering = ['-started_on']


admin.site.register(DomainCaseRuleRun, DomainCaseRuleRunAdmin)
